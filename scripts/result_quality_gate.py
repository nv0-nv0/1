from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = json.loads((ROOT / 'src' / 'data' / 'site.json').read_text(encoding='utf-8'))
PRODUCTS = {item['key']: item for item in SITE_DATA.get('products', [])}


def fetch(method: str, url: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, method=method, data=data)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    with urlopen(req, timeout=20) as res:
        body = res.read().decode('utf-8')
        ctype = res.headers.get('Content-Type', '')
        if 'application/json' in ctype:
            return res.status, json.loads(body)
        return res.status, body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_scorecard(scorecard: dict, *, product_key: str, stage: str) -> None:
    require((scorecard or {}).get('total') == 100, f'{product_key}:{stage}: total score not 100')
    require((scorecard or {}).get('earned') == 100, f'{product_key}:{stage}: earned score not 100')
    require(len((scorecard or {}).get('items') or []) >= 7, f'{product_key}:{stage}: scorecard items insufficient')
    for item in scorecard.get('items') or []:
        require(item.get('score') == item.get('max'), f'{product_key}:{stage}: dimension not maxed')
        require(len(item.get('reason') or '') >= 20, f'{product_key}:{stage}: scorecard reason too short')


def check_rich_outputs(items: list[dict], *, product_key: str, stage: str, minimum: int) -> None:
    require(len(items or []) >= minimum, f'{product_key}:{stage}: outputs insufficient')
    for item in items:
        require(len(item.get('title') or '') >= 3, f'{product_key}:{stage}: output title too short')
        require(len(item.get('preview') or '') >= 20, f'{product_key}:{stage}: output preview too short')
        require(len(item.get('whatIncluded') or '') >= 15, f'{product_key}:{stage}: output include note too short')
        require(len(item.get('actionNow') or '') >= 15, f'{product_key}:{stage}: output action note too short')
        require(len(item.get('buyerValue') or '') >= 15, f'{product_key}:{stage}: output buyer value too short')
        require(len(item.get('expertLens') or '') >= 15, f'{product_key}:{stage}: output expert lens too short')


def check_bundle(items: list[dict], *, product_key: str, stage: str, minimum: int) -> None:
    require(len(items or []) >= minimum, f'{product_key}:{stage}: bundle insufficient')
    for item in items:
        require(len(item.get('title') or '') >= 3, f'{product_key}:{stage}: bundle title too short')
        require(len(item.get('description') or '') >= 15, f'{product_key}:{stage}: bundle description too short')
        require(len(item.get('customerValue') or '') >= 10, f'{product_key}:{stage}: bundle customer value too short')
        require(len(item.get('usageMoment') or '') >= 2, f'{product_key}:{stage}: bundle usage moment too short')
        require(len(item.get('expertNote') or '') >= 10, f'{product_key}:{stage}: bundle expert note too short')


def check_product(base: str, product_key: str) -> dict[str, object]:
    product = PRODUCTS[product_key]
    demo_payload = {
        'product': product_key,
        'company': f'{product["name"]} Quality Lab',
        'name': '품질검증',
        'email': f'{product_key}-quality@example.com',
        'team': '1인 운영',
        'goal': product.get('problem') or product.get('summary'),
        'keywords': ', '.join((product.get('outputs') or [])[:3]),
        'plan': 'Growth',
    }
    _, demo = fetch('POST', f'{base}/api/public/demo-requests', demo_payload)
    preview = demo.get('preview') or {}
    check_scorecard(preview.get('scorecard') or {}, product_key=product_key, stage='demo')
    check_rich_outputs(preview.get('sampleOutputs') or [], product_key=product_key, stage='demo', minimum=min(3, len(product.get('outputs') or [])))
    require(len(preview.get('prioritySequence') or []) >= 3, f'{product_key}:demo: priority sequence insufficient')
    require(len(preview.get('expertNotes') or []) >= 2, f'{product_key}:demo: expert notes insufficient')
    require(len(preview.get('objectionHandling') or []) >= 2, f'{product_key}:demo: objection handling insufficient')
    require(len(preview.get('closingArgument') or '') >= 30, f'{product_key}:demo: closing argument too short')

    _, reserved = fetch('POST', f'{base}/api/public/orders/reserve', {
        'product': product_key,
        'plan': 'Growth',
        'billing': 'one-time',
        'paymentMethod': 'toss',
        'company': f'{product["name"]} Quality Lab',
        'name': '품질검증',
        'email': f'{product_key}-quality@example.com',
        'note': '체험 목표: 결과물 품질 검증\n키워드: 전문성, 설득력, 발행\n긴급도: 이번 주 안',
    })
    order = reserved['order']
    _, confirmed_res = fetch('POST', f'{base}/api/public/payments/toss/confirm', {
        'paymentKey': f'quality_{product_key}_payment',
        'orderId': order['id'],
        'amount': order['amount'],
    })
    confirmed = confirmed_res['order']
    if confirmed.get('status') == 'intake_required':
        intake_payload = {
            'company': f'{product["name"]} Quality Lab',
            'name': '품질검증',
            'email': f'{product_key}-quality@example.com',
            'note': '체험 목표: 결과물 품질 검증\n키워드: 전문성, 설득력, 발행\n긴급도: 이번 주 안',
        }
        if product_key == 'veridion':
            intake_payload['website'] = 'https://example.com'
        _, intake_res = fetch('POST', f"{base}/api/public/orders/{order['id']}/intake", intake_payload)
        confirmed = intake_res['order']
    require(confirmed.get('status') == 'delivered', f'{product_key}: order should be delivered after payment/intake')
    result_pack = confirmed.get('resultPack') or {}
    check_scorecard(result_pack.get('scorecard') or {}, product_key=product_key, stage='delivery')
    check_rich_outputs(result_pack.get('outputs') or [], product_key=product_key, stage='delivery', minimum=len(product.get('outputs') or []))
    check_bundle(result_pack.get('issuanceBundle') or [], product_key=product_key, stage='issuance', minimum=3)
    check_bundle(result_pack.get('deliveryAssets') or [], product_key=product_key, stage='delivery-assets', minimum=3)
    require(len(result_pack.get('prioritySequence') or []) >= 3, f'{product_key}:delivery: priority sequence insufficient')
    require(len(result_pack.get('expertNotes') or []) >= 2, f'{product_key}:delivery: expert notes insufficient')
    require(len(result_pack.get('objectionHandling') or []) >= 2, f'{product_key}:delivery: objection handling insufficient')
    require(len(result_pack.get('executiveSummary') or '') >= 40, f'{product_key}:delivery: executive summary too short')
    require(len(result_pack.get('valueNarrative') or '') >= 80, f'{product_key}:delivery: value narrative too short')
    require(len(result_pack.get('buyerDecisionReason') or '') >= 40, f'{product_key}:delivery: buyer decision reason too short')
    return {
        'product': product_key,
        'demoScore': preview.get('scorecard', {}).get('earned'),
        'deliveryScore': result_pack.get('scorecard', {}).get('earned'),
        'outputs': len(result_pack.get('outputs') or []),
        'issuance': len(result_pack.get('issuanceBundle') or []),
        'deliveryAssets': len(result_pack.get('deliveryAssets') or []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Quality gate for demo previews and issued result packs')
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    summary = [check_product(base, key) for key in PRODUCTS]
    print(json.dumps({'ok': True, 'products': summary}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'RESULT_QUALITY_GATE_FAIL: {exc}', file=sys.stderr)
        raise
