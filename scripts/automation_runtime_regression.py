from __future__ import annotations

import argparse
import json
import sys
from urllib.request import Request, urlopen


def fetch(url: str):
    req = Request(url, headers={"Accept": "application/json, text/html"})
    with urlopen(req, timeout=20) as res:
        body = res.read().decode("utf-8", errors="replace")
        ctype = res.headers.get("Content-Type", "")
        if "application/json" in ctype:
            return res.status, json.loads(body)
        return res.status, body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regression checks for full automation surfaces")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    status, page = fetch(f"{base}/admin/")
    require(status == 200, f"admin page status {status}")
    require('data-admin-action="toggle-payment"' not in page, 'manual toggle-payment button should not be exposed')
    require('data-admin-action="advance"' not in page, 'manual advance button should not be exposed')
    require('data-admin-action="republish"' not in page, 'manual republish button should not be exposed')
    require('샘플 데이터 생성' not in page, 'manual seed button should not be exposed')
    require('엔진 데이터 초기화' not in page, 'manual reset button should not be exposed')

    status, payload = fetch(f"{base}/api/public/system-config")
    require(status == 200 and payload.get('ok') is True, 'system config should be reachable')
    admin = (payload.get('config') or {}).get('admin') or {}
    require(admin.get('manualActionsEnabled') is False, 'manual admin actions should be disabled by default')

    status, success_page = fetch(f"{base}/payments/toss/success/")
    require(status == 200, f"payment success page status {status}")
    require('payment-success-result' in success_page, 'payment success shell missing')

    print(json.dumps({"ok": True, "checks": ["admin-ui-no-manual-buttons", "system-config-manual-actions-disabled", "payment-success-shell"]}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"AUTOMATION_RUNTIME_REGRESSION_FAIL: {exc}", file=sys.stderr)
        raise
