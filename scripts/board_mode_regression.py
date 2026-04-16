from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def fetch(method: str, url: str, payload: dict | None = None, headers: dict[str, str] | None = None):
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
            if "application/json" in ctype:
                return res.status, json.loads(body)
            return res.status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return exc.code, parsed


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Board-only regression checks")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--admin-token", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    admin_headers = {"X-Admin-Token": args.admin_token}

    for path in ('/', '/board/', '/admin/', '/api/health', '/api/public/board/feed'):
        status, _ = fetch('GET', base + path, headers=admin_headers if path.startswith('/admin') else None)
        require(status == 200, f'{path} should be 200 in board-only mode, got {status}')

    for path in ('/products/', '/pricing/', '/docs/', '/demo/', '/checkout/', '/portal/'):
        status, _ = fetch('GET', base + path)
        require(status == 410, f'{path} should be 410 in board-only mode, got {status}')

    for path, payload in (
        ('/api/public/demo-requests', {'product': 'veridion', 'company': 'Board', 'name': '테스터', 'email': 'board@example.com'}),
        ('/api/public/contact-requests', {'product': 'veridion', 'company': 'Board', 'email': 'board@example.com', 'issue': 'test'}),
        ('/api/public/orders/reserve', {'product': 'veridion', 'plan': 'Starter', 'billing': 'one-time', 'paymentMethod': 'toss', 'company': 'Board', 'name': '테스터', 'email': 'board@example.com'}),
        ('/api/public/portal/lookup', {'email': 'board@example.com', 'code': 'NV0-CHECK-000'}),
    ):
        status, body = fetch('POST', base + path, payload)
        require(status == 410, f'{path} should be 410 in board-only mode, got {status}')
        require(isinstance(body, dict) and body.get('mode') == 'board_only', f'{path} should return board_only json')

    status, body = fetch('GET', f'{base}/api/admin/state', headers=admin_headers)
    require(status == 200, f'admin state should be 200 in board-only mode, got {status}')
    require(body.get('ok') is True, 'admin state missing ok=true in board-only mode')

    print(json.dumps({'ok': True, 'checks': ['board-allowed-surfaces', 'board-disabled-pages', 'board-disabled-apis', 'board-admin']}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'BOARD_MODE_REGRESSION_FAIL: {exc}', file=sys.stderr)
        raise
