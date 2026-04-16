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
        return res.status, json.loads(body) if 'application/json' in ctype else body


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def analyze_payload(product_key: str) -> tuple[str, dict]:
    if product_key == 'clearport':
        return '/api/public/clearport/analyze', {
            'company': 'Cache Lab', 'submissionType': '정부·기관 서류 제출', 'targetOrg': '서울 테스트 기관',
            'deadline': '2026-04-30', 'teamSize': '1명', 'requiredDocs': ['사업자등록증', '통장사본', '인감증명'],
            'uploadedDocs': ['사업자등록증'], 'options': ['bizreg'], 'blocker': '날인 대기',
        }
    if product_key == 'grantops':
        return '/api/public/grantops/analyze', {
            'company': 'Cache Lab', 'programName': '테스트 지원사업', 'deadline': '2026-05-01',
            'teamSize': '1명', 'stage': '서류 제출', 'options': ['timeline', 'roles'], 'blocker': '자료 정리',
        }
    if product_key == 'draftforge':
        return '/api/public/draftforge/analyze', {
            'company': 'Cache Lab', 'docType': '제안서', 'approvalSteps': '3', 'channel': '이메일',
            'versionState': '혼재', 'draftPain': '최종본 혼선', 'options': ['final', 'review'],
        }
    raise RuntimeError(f'unsupported product for analyze cache: {product_key}')


def check_cache(base: str) -> list[dict[str, object]]:
    summary = []
    for product_key in ('clearport', 'grantops', 'draftforge'):
        endpoint, payload = analyze_payload(product_key)
        _, first = fetch('POST', f'{base}{endpoint}', payload)
        _, second = fetch('POST', f'{base}{endpoint}', payload)
        require(first.get('cached') is False, f'{product_key}: first analyze should not be cached')
        require(second.get('cached') is True, f'{product_key}: second analyze should be cached')
        require(first.get('report', {}).get('code') == second.get('report', {}).get('code'), f'{product_key}: cached report code mismatch')
        summary.append({'product': product_key, 'cached': True, 'reportCode': first.get('report', {}).get('code')})
    return summary


def check_idempotency(base: str) -> dict[str, object]:
    demo_payload = {
        'product': 'clearport', 'company': 'Idempotency Lab', 'name': '테스터', 'email': 'idem-demo@example.com',
        'team': '1인 운영', 'need': '반복 제출 방지 확인', 'keywords': '중복,안정성', 'plan': 'Growth',
    }
    _, demo1 = fetch('POST', f'{base}/api/public/demo-requests', demo_payload)
    _, demo2 = fetch('POST', f'{base}/api/public/demo-requests', demo_payload)
    require(demo1['demo']['id'] == demo2['demo']['id'], 'demo idempotency failed')

    contact_payload = {
        'product': 'grantops', 'company': 'Idempotency Lab', 'name': '테스터', 'email': 'idem-contact@example.com',
        'issue': '같은 문의 재전송 방지 확인',
    }
    _, con1 = fetch('POST', f'{base}/api/public/contact-requests', contact_payload)
    _, con2 = fetch('POST', f'{base}/api/public/contact-requests', contact_payload)
    require(con1['contact']['id'] == con2['contact']['id'], 'contact idempotency failed')

    order_payload = {
        'product': 'draftforge', 'plan': 'Growth', 'billing': 'one-time', 'paymentMethod': 'toss',
        'company': 'Idempotency Lab', 'name': '테스터', 'email': 'idem-order@example.com',
        'note': '같은 결제 예약 반복 전송 방지',
    }
    _, ord1 = fetch('POST', f'{base}/api/public/orders/reserve', order_payload)
    _, ord2 = fetch('POST', f'{base}/api/public/orders/reserve', order_payload)
    require(ord1['order']['id'] == ord2['order']['id'], 'order reserve idempotency failed')
    return {'demoId': demo1['demo']['id'], 'contactId': con1['contact']['id'], 'orderId': ord1['order']['id']}


def check_result_integrity(base: str) -> list[dict[str, object]]:
    rows = []
    for product_key in PRODUCTS:
        payload = {
            'product': product_key,
            'plan': 'Growth',
            'billing': 'one-time',
            'paymentMethod': 'toss',
            'company': f'{product_key} Integrity Lab',
            'name': '무결성테스터',
            'email': f'{product_key}-integrity@example.com',
            'note': '체험 목표: 발행본 무결성 확인\n키워드: 안정성,결과물,발행',
        }
        _, reserved = fetch('POST', f'{base}/api/public/orders/reserve', payload)
        order = reserved['order']
        _, confirmed = fetch('POST', f'{base}/api/public/payments/toss/confirm', {
            'paymentKey': f'mock_{product_key}_integrity', 'orderId': order['id'], 'amount': order['amount'],
        })
        paid = confirmed['order']
        pack = paid.get('resultPack') or {}
        require(bool(pack.get('artifactManifest')), f'{product_key}: artifact manifest missing')
        require(bool(pack.get('qualityValidation', {}).get('passed')), f'{product_key}: quality validation failed')
        require(pack.get('issuanceReadiness', {}).get('status') == 'ready', f'{product_key}: issuance readiness not ready')
        require(bool(pack.get('resultPackDigest')), f'{product_key}: result pack digest missing')
        require(bool(pack.get('supportGuide')), f'{product_key}: support guide missing')
        require(len(pack.get('recheckPlan') or []) >= 3, f'{product_key}: recheck plan missing')
        require(pack.get('issuanceReadiness', {}).get('publicationCount') == len(paid.get('publicationIds') or []), f'{product_key}: publication count mismatch')
        require(paid.get('deliveryMeta', {}).get('resultHash') == pack.get('resultPackDigest'), f'{product_key}: delivery hash mismatch')
        require(bool(paid.get('deliveryMeta', {}).get('qualityPassed')), f'{product_key}: delivery quality flag missing')
        rows.append({'product': product_key, 'digest': pack.get('resultPackDigest')[:12], 'publicationCount': len(paid.get('publicationIds') or [])})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description='Regression for performance/stability/result issuance hardening')
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    result = {
        'ok': True,
        'cache': check_cache(base),
        'idempotency': check_idempotency(base),
        'integrity': check_result_integrity(base),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'RUNTIME_HARDENING_REGRESSION_FAIL: {exc}', file=sys.stderr)
        raise
