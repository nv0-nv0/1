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
    with urlopen(req, timeout=20) as res:
        body = res.read().decode('utf-8')
        ctype = res.headers.get('Content-Type', '')
        return res.status, json.loads(body) if 'application/json' in ctype else body


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def check_clearport(base: str) -> dict[str, object]:
    payload = {
        'company': 'Clearport Runtime Lab', 'submissionType': '정부·기관 서류 제출', 'targetOrg': '서울시 테스트 기관',
        'deadline': '2026-04-25', 'teamSize': '1명', 'requiredDocs': ['사업자등록증', '통장사본', '인감증명'],
        'uploadedDocs': ['사업자등록증'], 'options': ['bizreg'], 'blocker': '날인 대기',
    }
    _, res = fetch('POST', f'{base}/api/public/clearport/analyze', payload)
    report = res.get('report') or {}
    require('copySuggestions' not in report, 'clearport: public report leaked templates')
    require('documentChecklist' not in report, 'clearport: public report leaked full checklist')
    require(bool(report.get('publicLocked')), 'clearport: public lock missing')
    require(len(report.get('issues') or []) <= 3, 'clearport: public issues not masked')
    reserve = {
        'product': 'clearport', 'plan': 'Growth', 'billing': 'one-time', 'paymentMethod': 'toss', 'company': 'Clearport Runtime Lab',
        'name': '통합테스터', 'email': 'clearport-surface@example.com', 'reportId': report.get('id'), 'reportCode': report.get('code'),
        'note': '체험 목표: 제출 막힘 제거\n키워드: 체크리스트,회신,운영\n긴급도: 이번 주',
    }
    _, reserved = fetch('POST', f'{base}/api/public/orders/reserve', reserve)
    order = reserved['order']
    _, confirmed = fetch('POST', f'{base}/api/public/payments/toss/confirm', {'paymentKey': 'mock_clearport_surface', 'orderId': order['id'], 'amount': order['amount']})
    pack = confirmed['order'].get('resultPack') or {}
    require(bool(pack.get('documentChecklist')), 'clearport: paid pack missing checklist')
    require(bool(pack.get('responseTemplates')), 'clearport: paid pack missing response templates')
    require(bool(pack.get('executionPlan')), 'clearport: paid pack missing execution plan')
    require(bool(pack.get('qaChecklist')), 'clearport: paid pack missing qa checklist')
    return {'product': 'clearport', 'reportCode': report.get('code'), 'orderCode': confirmed['order'].get('code')}


def check_grantops(base: str) -> dict[str, object]:
    payload = {
        'company': 'Grantops Runtime Lab', 'projectName': '2026 디지털 전환 공모', 'deadline': '2026-04-28', 'progress': '초안 작성 중',
        'contributors': '1명', 'delayPoint': '증빙 수집', 'teamMembers': ['실무', '검토'], 'options': ['review', 'evidence'],
    }
    _, res = fetch('POST', f'{base}/api/public/grantops/analyze', payload)
    report = res.get('report') or {}
    require('schedule' not in report, 'grantops: public report leaked full schedule')
    require('rolePlan' not in report, 'grantops: public report leaked role plan')
    require('copySuggestions' not in report, 'grantops: public report leaked templates')
    require(bool(report.get('publicLocked')), 'grantops: public lock missing')
    require(len(report.get('issues') or []) <= 3, 'grantops: public issues not masked')
    reserve = {
        'product': 'grantops', 'plan': 'Growth', 'billing': 'one-time', 'paymentMethod': 'toss', 'company': 'Grantops Runtime Lab',
        'name': '통합테스터', 'email': 'grantops-surface@example.com', 'reportId': report.get('id'), 'reportCode': report.get('code'),
        'note': '체험 목표: 마감 안정화\n키워드: 일정,역할,요청\n긴급도: 이번 주',
    }
    _, reserved = fetch('POST', f'{base}/api/public/orders/reserve', reserve)
    order = reserved['order']
    _, confirmed = fetch('POST', f'{base}/api/public/payments/toss/confirm', {'paymentKey': 'mock_grantops_surface', 'orderId': order['id'], 'amount': order['amount']})
    pack = confirmed['order'].get('resultPack') or {}
    require(bool(pack.get('scheduleLocks')), 'grantops: paid pack missing schedule locks')
    require(bool(pack.get('roleAssignments')), 'grantops: paid pack missing role assignments')
    require(bool(pack.get('requestTemplates')), 'grantops: paid pack missing request templates')
    require(bool(pack.get('criticalPath')), 'grantops: paid pack missing critical path')
    require(bool(pack.get('qaChecklist')), 'grantops: paid pack missing qa checklist')
    return {'product': 'grantops', 'reportCode': report.get('code'), 'orderCode': confirmed['order'].get('code')}


def check_draftforge(base: str) -> dict[str, object]:
    payload = {
        'company': 'Draftforge Runtime Lab', 'docType': '제안서', 'approvalSteps': '3단계', 'channel': '이메일',
        'draftPain': '최종본 혼선', 'versions': ['v1', 'v2-final', 'v3-final-final'], 'approvers': ['실무', '팀장', '대표'], 'options': ['final', 'review'],
    }
    _, res = fetch('POST', f'{base}/api/public/draftforge/analyze', payload)
    report = res.get('report') or {}
    require('versionMatrix' not in report, 'draftforge: public report leaked version matrix')
    require('copySuggestions' not in report, 'draftforge: public report leaked templates')
    require(bool(report.get('publicLocked')), 'draftforge: public lock missing')
    require(len(report.get('issues') or []) <= 3, 'draftforge: public issues not masked')
    reserve = {
        'product': 'draftforge', 'plan': 'Growth', 'billing': 'one-time', 'paymentMethod': 'toss', 'company': 'Draftforge Runtime Lab',
        'name': '통합테스터', 'email': 'draftforge-surface@example.com', 'reportId': report.get('id'), 'reportCode': report.get('code'),
        'note': '체험 목표: 최종본 기준 확정\n키워드: 버전,승인,배포\n긴급도: 이번 주',
    }
    _, reserved = fetch('POST', f'{base}/api/public/orders/reserve', reserve)
    order = reserved['order']
    _, confirmed = fetch('POST', f'{base}/api/public/payments/toss/confirm', {'paymentKey': 'mock_draftforge_surface', 'orderId': order['id'], 'amount': order['amount']})
    pack = confirmed['order'].get('resultPack') or {}
    require(bool(pack.get('versionRules')), 'draftforge: paid pack missing version rules')
    require(bool(pack.get('copyTemplates')), 'draftforge: paid pack missing copy templates')
    require(bool(pack.get('approvalFlow')), 'draftforge: paid pack missing approval flow')
    require(bool(pack.get('releaseChecklist')), 'draftforge: paid pack missing release checklist')
    require(bool(pack.get('executionPlan')), 'draftforge: paid pack missing execution plan')
    return {'product': 'draftforge', 'reportCode': report.get('code'), 'orderCode': confirmed['order'].get('code')}


def main() -> None:
    parser = argparse.ArgumentParser(description='Public surface masking and paid pack enrichment regression for non-Veridion products')
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    results = [check_clearport(base), check_grantops(base), check_draftforge(base)]
    print(json.dumps({'ok': True, 'products': results}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'PRODUCT_SURFACE_REGRESSION_FAIL: {exc}', file=sys.stderr)
        raise
