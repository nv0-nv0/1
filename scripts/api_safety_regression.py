from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def fetch(method: str, url: str, payload: dict | None = None, headers: dict[str, str] | None = None, *, with_headers: bool = False):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, method=method, data=data)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=20) as res:
            body = res.read().decode("utf-8")
            ctype = res.headers.get("Content-Type", "")
            parsed = json.loads(body) if "application/json" in ctype else body
            if with_headers:
                return res.status, parsed, dict(res.headers.items())
            return res.status, parsed
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        if with_headers:
            return exc.code, parsed, dict(exc.headers.items())
        return exc.code, parsed


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regression checks for safety, negative paths, and idempotency")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--admin-token", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    admin_headers = {"X-Admin-Token": args.admin_token}

    status, body = fetch("GET", f"{base}/api/admin/state")
    require(status == 401, f"admin state without token should be 401, got {status}")
    require(isinstance(body, dict) and body.get("detail"), "admin 401 should return json detail")

    status, body, headers = fetch("GET", f"{base}/api/health", with_headers=True)
    require(status == 200, f"health should be 200, got {status}")
    lower_headers = {str(k).lower(): v for k, v in headers.items()}
    require('server' not in lower_headers, 'Server header should be disabled in uvicorn')
    require('date' not in lower_headers, 'Date header should be disabled in uvicorn')

    status, body = fetch("GET", f"{base}/api/health", headers={"Host": "evil.example.com"})
    require(status == 400, f"invalid host should be 400, got {status}")

    status, _ = fetch("POST", f"{base}/api/public/demo-requests", {
        "product": "veridion", "company": "Bad Input", "name": "테스터", "email": "not-an-email"
    })
    require(status == 400, f"invalid demo email should be 400, got {status}")

    status, _ = fetch("POST", f"{base}/api/public/contact-requests", {
        "product": "clearport", "company": "Bad Input", "email": "test@example.com", "issue": ""
    })
    require(status == 400, f"blank contact issue should be 400, got {status}")

    status, _ = fetch("POST", f"{base}/api/public/portal/lookup", {
        "email": "invalid", "code": "NV0-CHECK-000"
    })
    require(status == 400, f"invalid portal email should be 400, got {status}")

    status, _ = fetch("POST", f"{base}/api/public/orders/reserve", {
        "product": "grantops", "plan": "Nope", "billing": "one-time", "paymentMethod": "toss",
        "company": "Bad Input", "name": "테스터", "email": "bad@example.com"
    })
    require(status == 400, f"invalid plan should be 400, got {status}")

    status, body = fetch("POST", f"{base}/api/public/orders/reserve", {
        "product": "veridion", "plan": "Growth", "billing": "one-time", "paymentMethod": "toss",
        "company": "Safety Lab", "name": "테스터", "email": "safety@example.com",
        "note": "체험 목표: 안전 회귀 검증\n키워드: 검증,중복결제,웹훅\n긴급도: 이번 주"
    })
    require(status == 200, f"order reserve failed with {status}")
    order = body["order"]

    status, _ = fetch("POST", f"{base}/api/public/payments/toss/confirm", {
        "paymentKey": f"wrong_{order['id']}", "orderId": order["id"], "amount": int(order["amount"]) + 1,
    })
    require(status == 400, f"wrong amount confirm should be 400, got {status}")

    status, body = fetch("POST", f"{base}/api/public/payments/toss/confirm", {
        "paymentKey": f"mock_{order['id']}", "orderId": order["id"], "amount": order["amount"],
    })
    require(status == 200, f"payment confirm failed with {status}")
    confirmed = body["order"]
    require(confirmed.get("paymentStatus") == "paid", "payment confirm did not set paid")

    status, body = fetch("POST", f"{base}/api/public/payments/toss/confirm", {
        "paymentKey": f"mock_{order['id']}", "orderId": order["id"], "amount": order["amount"],
    })
    require(status == 200, f"idempotent confirm should be 200, got {status}")
    require(body["order"].get("paymentStatus") == "paid", "idempotent confirm lost paid state")

    status, _ = fetch("POST", f"{base}/api/public/payments/toss/confirm", {
        "paymentKey": f"another_{order['id']}", "orderId": order["id"], "amount": order["amount"],
    })
    require(status == 409, f"different payment key should be 409, got {status}")

    status, body = fetch("POST", f"{base}/api/public/payments/toss/webhook", {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "eventId": f"evt_{order['id']}",
        "orderId": order["id"],
        "data": {
            "orderId": order["id"],
            "status": "DONE",
            "paymentKey": confirmed.get("paymentKey"),
            "secret": ((confirmed.get("paymentMeta") or {}).get("secret")),
        },
    })
    require(status == 200, f"payment webhook should be 200, got {status}")
    require(body.get("ignored") is False, "first webhook should update order")

    status, body = fetch("POST", f"{base}/api/public/payments/toss/webhook", {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "eventId": f"evt_{order['id']}",
        "orderId": order["id"],
        "data": {
            "orderId": order["id"],
            "status": "DONE",
            "paymentKey": confirmed.get("paymentKey"),
            "secret": ((confirmed.get("paymentMeta") or {}).get("secret")),
        },
    })
    require(status == 200, f"duplicate webhook should be 200, got {status}")
    require(body.get("ignored") is True and body.get("reason") == "duplicate_webhook", "duplicate webhook not ignored")

    status, body = fetch("GET", f"{base}/api/admin/export", headers=admin_headers)
    require(status == 200, f"admin export failed with {status}")
    exported = body
    require(exported.get("ok") is True and isinstance(exported.get("state"), dict), "admin export missing state payload")
    minimal_import = {
        "replace": False,
        "state": {
            "scheduler": (exported.get("state") or {}).get("scheduler", [])[:1],
            "publications": (exported.get("state") or {}).get("publications", [])[:1],
        },
    }
    status, body = fetch("POST", f"{base}/api/admin/import", minimal_import, headers=admin_headers)
    require(status == 200, f"admin import failed with {status}")
    require(body.get("ok") is True, "admin import missing ok=true")

    req = Request(f"{base}/api/public/contact-requests", method="POST", data=b"{}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", "9999999")
    try:
        with urlopen(req, timeout=20) as res:
            code = res.status
            body_text = res.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        code = exc.code
        body_text = exc.read().decode("utf-8", errors="replace")
    require(code == 413, f"oversized request should be 413, got {code}: {body_text}")

    print(json.dumps({
        "ok": True,
        "checks": [
            "admin-auth-guard", "header-hardening", "invalid-host-guard", "input-validation", "payment-idempotency",
            "webhook-duplicate-guard", "admin-export-import", "body-size-guard"
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"API_SAFETY_REGRESSION_FAIL: {exc}", file=sys.stderr)
        raise
