from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def fetch(method: str, url: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, method=method, data=data)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=15) as res:
        body = res.read().decode('utf-8')
        ctype = res.headers.get('Content-Type', '')
        if 'application/json' in ctype:
            return res.status, json.loads(body), body
        return res.status, body, body


def expect_status(url: str, status: int) -> None:
    try:
        actual, _, _ = fetch('GET', url)
    except HTTPError as exc:
        actual = exc.code
    if actual != status:
        raise RuntimeError(f'{url} expected {status}, got {actual}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Smoke test for deployed NV0 instance')
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--mode', choices=['full', 'board'], required=True)
    parser.add_argument('--admin-token', default='')
    args = parser.parse_args()

    base = args.base_url.rstrip('/')
    admin_headers = {'X-Admin-Token': args.admin_token} if args.admin_token else {}

    status, health, _ = fetch('GET', base + '/api/health')
    if status != 200 or not health.get('ok'):
        raise RuntimeError('health check failed')

    _, system_cfg, _ = fetch('GET', base + '/api/public/system-config')
    cfg = system_cfg['config']

    expect_status(base + '/', 200)
    expect_status(base + '/board/', 200)
    expect_status(base + '/admin/', 200)
    expect_status(base + '/legal/privacy/', 200)

    summary: dict[str, object] = {
        'serviceMode': health.get('serviceMode'),
        'boardOnly': cfg.get('boardOnly'),
        'paymentProvider': cfg.get('payment', {}).get('provider'),
    }

    if args.mode == 'board':
        for path in ['/products/', '/checkout/', '/portal/', '/demo/', '/contact/']:
            expect_status(base + path, 410)
        _, feed, _ = fetch('GET', base + '/api/public/board/feed')
        summary['boardFeedCount'] = len(feed.get('items', []))
    else:
        for path in ['/products/', '/products/veridion/', '/checkout/', '/portal/', '/demo/', '/contact/', '/payments/toss/success/']:
            expect_status(base + path, 200)
        _, demo, _ = fetch('POST', base + '/api/public/demo-requests', {
            'product': 'veridion',
            'company': 'Smoke Labs',
            'name': 'Smoke User',
            'email': 'smoke@example.com',
            'team': '1인',
            'need': '배포 직후 즉시 시연 확인',
        })
        _, contact, _ = fetch('POST', base + '/api/public/contact-requests', {
            'product': 'veridion',
            'company': 'Smoke Labs',
            'email': 'smoke@example.com',
            'issue': '배포 직후 문의 흐름 확인',
        })
        _, reserved, _ = fetch('POST', base + '/api/public/orders/reserve', {
            'product': 'veridion',
            'plan': 'Starter',
            'billing': 'one-time',
            'paymentMethod': 'toss',
        })
        summary['demoCode'] = demo['demo']['code']
        summary['contactCode'] = contact['contact']['code']
        summary['orderCode'] = reserved['order']['code']
        if cfg.get('payment', {}).get('toss', {}).get('mock'):
            _, confirmed, _ = fetch('POST', base + '/api/public/payments/toss/confirm', {
                'paymentKey': 'mock_smoke_payment',
                'orderId': reserved['order']['id'],
                'amount': reserved['order']['amount'],
            })
            summary['orderStatusAfterConfirm'] = confirmed['order']['status']
            _, completed, _ = fetch('POST', base + f"/api/public/orders/{confirmed['order']['id']}/intake", {
                'company': 'Smoke Labs',
                'name': 'Smoke User',
                'email': 'smoke@example.com',
                'website': 'https://example.com',
                'note': 'smoke-check',
            })
            _, lookup, _ = fetch('POST', base + '/api/public/portal/lookup', {
                'email': completed['order']['email'],
                'code': completed['order']['code'],
            })
            summary['publicationCount'] = len(lookup.get('publications', []))
            summary['orderStatus'] = completed['order']['status']
        else:
            summary['orderStatus'] = reserved['order']['status']
            summary['note'] = 'Toss live mode detected: reserve only smoke tested. Run one real payment separately.'

    if args.admin_token:
        _, state, _ = fetch('GET', base + '/api/admin/state', headers=admin_headers)
        summary['adminStateKeys'] = sorted(state.keys())

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'SMOKE_FAIL: {exc}', file=sys.stderr)
        raise
