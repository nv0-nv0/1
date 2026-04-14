from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = json.loads((ROOT / 'src' / 'data' / 'site.json').read_text(encoding='utf-8'))
PRODUCTS = {item['key']: item for item in SITE_DATA.get('products', [])}


def fetch(method: str, url: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, method=method, data=data)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=20) as res:
        body = res.read().decode('utf-8')
        ctype = res.headers.get('Content-Type', '')
        if 'application/json' in ctype:
            return res.status, json.loads(body)
        return res.status, body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_product(base: str, product_key: str) -> dict[str, object]:
    product = PRODUCTS[product_key]
    status, _ = fetch('GET', f'{base}/products/{product_key}/')
    require(status == 200, f'{product_key}: product page not reachable')
    status, _ = fetch('GET', f'{base}/products/{product_key}/demo/')
    require(status == 200, f'{product_key}: demo page not reachable')

    demo_payload = {
        'product': product_key,
        'company': f'{product["name"]} Labs',
        'name': '통합테스터',
        'email': f'{product_key}@example.com',
        'team': '1인 운영',
        'need': f'{product["headline"]} 기준 즉시 데모 검증',
        'keywords': ', '.join((product.get('outputs') or [])[:3]),
        'plan': 'Growth',
    }
    _, demo_res = fetch('POST', f'{base}/api/public/demo-requests', demo_payload)
    preview = demo_res.get('preview') or {}
    require(demo_res.get('demo', {}).get('product') == product_key, f'{product_key}: demo product mismatch')
    require(len(preview.get('sampleOutputs') or []) >= min(3, len(product.get('outputs') or [])), f'{product_key}: demo preview outputs too short')
    require(len(preview.get('quickWins') or []) >= 2, f'{product_key}: demo quick wins missing')
    require(len(preview.get('valueDrivers') or []) >= 2, f'{product_key}: demo value drivers missing')
    require((preview.get('scorecard') or {}).get('earned') == 100, f'{product_key}: demo scorecard not 100')
    require(len(preview.get('prioritySequence') or []) >= 3, f'{product_key}: demo priority sequence missing')
    require(len(preview.get('expertNotes') or []) >= 2, f'{product_key}: demo expert notes missing')
    for item in (preview.get('sampleOutputs') or []):
        require(len(item.get('preview') or '') >= 20, f'{product_key}: demo output preview too short')
        require(len(item.get('whatIncluded') or '') >= 15, f'{product_key}: demo output include note too short')
        require(len(item.get('actionNow') or '') >= 15, f'{product_key}: demo output action note too short')
        require(len(item.get('buyerValue') or '') >= 15, f'{product_key}: demo output buyer value too short')

    order_payload = {
        'product': product_key,
        'plan': 'Growth',
        'billing': 'one-time',
        'paymentMethod': 'toss',
        'company': f'{product["name"]} Labs',
        'name': '통합테스터',
        'email': f'{product_key}@example.com',
        'note': '체험 목표: 즉시 작동 검증\n키워드: 결과물, 발행, 가치\n긴급도: 이번 주 안',
    }
    _, reserve_res = fetch('POST', f'{base}/api/public/orders/reserve', order_payload)
    order = reserve_res['order']
    require(order.get('product') == product_key, f'{product_key}: reserve product mismatch')
    _, confirm_res = fetch('POST', f'{base}/api/public/payments/toss/confirm', {
        'paymentKey': f'mock_{product_key}_payment',
        'orderId': order['id'],
        'amount': order['amount'],
    })
    confirmed = confirm_res['order']
    require(confirmed.get('status') == 'delivered', f'{product_key}: order not delivered')
    require(confirmed.get('paymentStatus') == 'paid', f'{product_key}: order not paid')
    result_pack = confirmed.get('resultPack') or {}
    require(len(result_pack.get('outputs') or []) >= len(product.get('outputs') or []), f'{product_key}: result outputs incomplete')
    require(len(result_pack.get('quickWins') or []) >= 3, f'{product_key}: result quick wins insufficient')
    require(len(result_pack.get('valueDrivers') or []) >= 3, f'{product_key}: value drivers insufficient')
    require(len(result_pack.get('successMetrics') or []) >= 3, f'{product_key}: success metrics insufficient')
    require((result_pack.get('scorecard') or {}).get('earned') == 100, f'{product_key}: result scorecard not 100')
    require(len(result_pack.get('prioritySequence') or []) >= 3, f'{product_key}: result priority sequence missing')
    require(len(result_pack.get('expertNotes') or []) >= 2, f'{product_key}: result expert notes missing')
    require(len(result_pack.get('issuanceBundle') or []) >= 3, f'{product_key}: issuance bundle insufficient')
    require(len(result_pack.get('deliveryAssets') or []) >= 3, f'{product_key}: delivery assets insufficient')
    require(len(result_pack.get('valueNarrative') or '') >= 80, f'{product_key}: value narrative too short')
    for item in (result_pack.get('outputs') or []):
        require(len(item.get('preview') or '') >= 20, f'{product_key}: result output preview too short')
        require(len(item.get('whatIncluded') or '') >= 15, f'{product_key}: result output include note too short')
        require(len(item.get('actionNow') or '') >= 15, f'{product_key}: result output action note too short')
        require(len(item.get('buyerValue') or '') >= 15, f'{product_key}: result output buyer value too short')
    for item in (result_pack.get('issuanceBundle') or []):
        require(len(item.get('description') or '') >= 15, f'{product_key}: issuance description too short')
        require(len(item.get('customerValue') or '') >= 10, f'{product_key}: issuance customer value too short')
    require(len(confirmed.get('publicationIds') or []) >= 2, f'{product_key}: publications not generated')

    _, lookup_res = fetch('POST', f'{base}/api/public/portal/lookup', {
        'email': confirmed['email'],
        'code': confirmed['code'],
    })
    looked_up = lookup_res.get('order') or {}
    publications = lookup_res.get('publications') or []
    require(looked_up.get('product') == product_key, f'{product_key}: portal product mismatch')
    require(len(publications) >= 2, f'{product_key}: portal publications missing')

    return {
        'product': product_key,
        'demoCode': demo_res.get('demo', {}).get('code'),
        'orderCode': confirmed.get('code'),
        'publicationCount': len(publications),
        'resultOutputCount': len(result_pack.get('outputs') or []),
        'issuanceCount': len(result_pack.get('issuanceBundle') or []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='End-to-end product runtime matrix for all NV0 products')
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    summary = [check_product(base, key) for key in PRODUCTS]
    print(json.dumps({'ok': True, 'products': summary}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'PRODUCT_RUNTIME_E2E_FAIL: {exc}', file=sys.stderr)
        raise
