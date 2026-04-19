from __future__ import annotations

import argparse
import json
import sys
from urllib.request import Request, urlopen

SENSITIVE_MARKERS = ('"accounts"', '"sessions"', 'passwordHash', 'token')


def fetch(method: str, url: str, payload: dict | None = None) -> tuple[int, bytes, dict]:
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, method=method, data=data)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    with urlopen(req, timeout=90) as res:
        body = res.read()
        return res.status, body, json.loads(body.decode('utf-8'))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description='Public payload size/leak regression checks')
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--max-scan-bytes', type=int, default=250000)
    parser.add_argument('--max-demo-bytes', type=int, default=50000)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')

    status, scan_body, payload = fetch('POST', f'{base}/api/public/veridion/scan', {
        'website': 'https://example.com',
        'industry': 'commerce',
        'country': 'KR',
        'focus': '전체 리스크 빠르게 보기',
    })
    require(status == 200, f'scan status should be 200, got {status}')
    require(len(scan_body) <= args.max_scan_bytes, f'scan payload too large: {len(scan_body)} bytes')
    text = scan_body.decode('utf-8')
    for marker in SENSITIVE_MARKERS:
        require(marker not in text, f'scan payload leaked marker: {marker}')
    require('state' not in payload, 'scan payload should not include state')
    require(payload.get('ok') is True, 'scan payload missing ok=true')

    status, demo_body, payload = fetch('POST', f'{base}/api/public/demo-requests', {
        'product': 'veridion',
        'company': 'Payload Test',
        'name': 'Tester',
        'email': 'payload-test@example.com',
        'need': 'payload regression',
    })
    require(status == 200, f'demo request status should be 200, got {status}')
    require(len(demo_body) <= args.max_demo_bytes, f'demo request payload too large: {len(demo_body)} bytes')
    text = demo_body.decode('utf-8')
    for marker in SENSITIVE_MARKERS:
        require(marker not in text, f'demo request payload leaked marker: {marker}')
    require('state' not in payload, 'demo request payload should not include state')
    require(payload.get('ok') is True, 'demo request payload missing ok=true')

    print(json.dumps({
        'ok': True,
        'scanBytes': len(scan_body),
        'demoBytes': len(demo_body),
        'scanStateIncluded': False,
        'demoStateIncluded': False,
    }, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'PUBLIC_PAYLOAD_REGRESSION_FAIL: {exc}', file=sys.stderr)
        raise
