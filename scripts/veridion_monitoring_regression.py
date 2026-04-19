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
        return res.status, json.loads(body)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description='Veridion monthly monitoring plan regression')
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')

    _, reserve = fetch('POST', f'{base}/api/public/orders/reserve', {
        'product': 'veridion',
        'plan': 'Monitor',
        'billing': 'monthly',
        'paymentMethod': 'toss',
    })
    order = reserve['order']
    require(order.get('billing') == 'monthly', 'reserve billing mismatch')
    require(order.get('amount') == 190000, 'reserve amount mismatch')

    _, confirm = fetch('POST', f'{base}/api/public/payments/toss/confirm', {
        'paymentKey': 'mock_monitor_monthly',
        'orderId': order['id'],
        'amount': order['amount'],
    })
    order = confirm['order']
    require(order.get('status') == 'intake_required', 'monitor order should await intake')

    _, intake = fetch('POST', f"{base}/api/public/orders/{order['id']}/intake", {
        'company': 'Monitor Labs',
        'name': '월간테스터',
        'email': 'monitor@example.com',
        'website': 'https://example.com',
        'country': 'KR',
        'note': '월 구독형 알림 검증',
    })
    order = intake['order']
    pack = order.get('resultPack') or {}
    monitoring = pack.get('monitoringSubscription') or {}
    require(order.get('status') == 'delivered', 'monitor order not delivered')
    require(bool(order.get('subscriptionActive')), 'subscriptionActive missing')
    require(bool(monitoring.get('enabled')), 'monitoring subscription missing')
    require(len(monitoring.get('watchSources') or []) >= 3, 'watch sources missing')
    require(len(monitoring.get('notificationChannels') or []) >= 2, 'notification channels missing')
    require(len(monitoring.get('changeSignals') or []) >= 3, 'change signals missing')
    require(len(pack.get('issuanceBundle') or []) >= 4, 'issuance bundle should include monitoring')
    print(json.dumps({
        'ok': True,
        'orderCode': order.get('code'),
        'billing': order.get('billing'),
        'amount': order.get('amount'),
        'watchSources': len(monitoring.get('watchSources') or []),
        'issuanceCount': len(pack.get('issuanceBundle') or []),
        'notificationChannels': len(monitoring.get('notificationChannels') or []),
    }, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'VERIDION_MONITORING_REGRESSION_FAIL: {exc}', file=sys.stderr)
        raise
