from __future__ import annotations

import argparse
import json
import sys
from urllib.request import Request, urlopen


def fetch(method: str, url: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(url, method=method, data=data)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    with urlopen(req, timeout=60) as res:
        body = res.read().decode('utf-8')
        ctype = res.headers.get('Content-Type', '')
        return res.status, json.loads(body) if 'application/json' in ctype else body


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description='Regression check for Veridion demo -> payment -> delivery runtime')
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')

    scan_payload = {
        'website': base,
        'company': 'Veridion Runtime Lab',
        'industry': 'saas',
        'market': 'kr',
        'focus': 'checkout',
    }
    status, body = fetch('POST', f'{base}/api/public/veridion/scan', scan_payload)
    require(status == 200, f'veridion scan should be 200, got {status}')
    require(body.get('ok') is True, 'veridion scan missing ok=true')
    report = body.get('report') or {}
    risk = report.get('risk') or {}
    require(isinstance(risk.get('riskScore'), int), 'public risk score missing')
    require((risk.get('estimatedExposure') or {}).get('display'), 'public exposure display missing')
    require(report.get('publicLocked', {}).get('message'), 'public locked message missing')
    require('siteSpecificRules' not in report, 'public report should not expose siteSpecificRules')
    require('pageActions' not in report, 'public report should not expose pageActions')
    require('remediationPlan' not in report, 'public report should not expose remediationPlan')
    require('pages' not in report, 'public report should not expose page records')
    require('copySuggestions' not in report, 'public report should not expose copy suggestions')
    require(len(report.get('topIssues') or []) >= 1, 'public report should expose at least one top issue')

    reserve_payload = {
        'product': 'veridion',
        'plan': 'Growth',
        'billing': 'one-time',
        'paymentMethod': 'toss',
        'company': 'Veridion Runtime Lab',
        'name': '통합테스터',
        'email': 'veridion-runtime@example.com',
        'reportId': report.get('id'),
        'reportCode': report.get('code'),
        'note': '체험 목표: Veridion 전체 발행 검증\n키워드: 리포트,규칙,발행\n긴급도: 이번 주',
    }
    status, body = fetch('POST', f'{base}/api/public/orders/reserve', reserve_payload)
    require(status == 200, f'veridion reserve should be 200, got {status}')
    order = body.get('order') or {}
    require(order.get('product') == 'veridion', 'reserved order product mismatch')

    status, body = fetch('POST', f'{base}/api/public/payments/toss/confirm', {
        'paymentKey': f'mock_{order.get("id")}',
        'orderId': order.get('id'),
        'amount': order.get('amount'),
    })
    require(status == 200, f'veridion confirm should be 200, got {status}')
    confirmed = body.get('order') or {}
    require(confirmed.get('status') == 'intake_required', 'veridion order should require intake after payment')
    require(confirmed.get('paymentStatus') == 'paid', 'veridion order should be paid after payment')

    status, body = fetch('POST', f'{base}/api/public/orders/{confirmed.get("id")}/intake', {
        'company': 'Veridion Runtime Lab',
        'name': '통합테스터',
        'email': 'veridion-runtime@example.com',
        'website': base,
        'note': '체험 목표: Veridion 전체 발행 검증\n키워드: 리포트,규칙,발행\n긴급도: 이번 주',
    })
    require(status == 200, f'veridion intake should be 200, got {status}')
    confirmed = body.get('order') or {}
    require(confirmed.get('status') == 'delivered', 'veridion order should be delivered after intake')
    pack = confirmed.get('resultPack') or {}
    require(isinstance(pack.get('siteSpecificRules'), list) and len(pack.get('siteSpecificRules') or []) >= 3, 'delivery pack siteSpecificRules missing')
    require(isinstance(pack.get('pageActions'), list) and len(pack.get('pageActions') or []) >= 3, 'delivery pack pageActions missing')
    require(isinstance(pack.get('remediationPlan'), list) and len(pack.get('remediationPlan') or []) >= 3, 'delivery pack remediationPlan missing')
    require((pack.get('penaltyExposure') or {}).get('display'), 'delivery pack penaltyExposure missing')
    require(len(pack.get('lawGroupSummary') or []) >= 1, 'delivery pack law group summary missing')
    require(isinstance((pack.get('linkedReport') or {}).get('riskScore'), int), 'delivery pack linked report risk score missing')
    require((pack.get('linkedReport') or {}).get('code') == report.get('code'), 'delivery pack should be linked to scanned report code')

    status, body = fetch('POST', f'{base}/api/public/portal/lookup', {
        'email': confirmed.get('email'),
        'code': confirmed.get('code'),
    })
    require(status == 200, f'portal lookup should be 200, got {status}')
    looked_up = body.get('order') or {}
    require(looked_up.get('product') == 'veridion', 'portal lookup product mismatch')

    print(json.dumps({
        'ok': True,
        'reportCode': report.get('code'),
        'riskScore': risk.get('riskScore'),
        'publicIssueCount': len(report.get('topIssues') or []),
        'deliveryRuleCount': len(pack.get('siteSpecificRules') or []),
        'deliveryPageActionCount': len(pack.get('pageActions') or []),
        'deliveryRemediationCount': len(pack.get('remediationPlan') or []),
        'exposure': (pack.get('penaltyExposure') or {}).get('display'),
    }, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'VERIDION_RUNTIME_REGRESSION_FAIL: {exc}', file=sys.stderr)
        raise
