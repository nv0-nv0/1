from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PORT = 8045
BASE = f'http://127.0.0.1:{PORT}'
DATA_DIR = ROOT / '.testdata_product_surface'
ADMIN_TOKEN = 'admin-test-token-abcdefghijklmnopqrstuvwxyz1234'
BACKUP_PASSPHRASE = 'test-backup-passphrase-1234567890-abcdef'
SITE_DATA = json.loads((ROOT / 'src' / 'data' / 'site.json').read_text(encoding='utf-8'))
PRODUCTS = SITE_DATA['products']


def http_json(method: str, path: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE + path, data=data, method=method)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=12) as res:
        body = res.read().decode('utf-8')
        return res.status, json.loads(body) if body else None, dict(res.headers)


def http_text(path: str) -> str:
    with urlopen(BASE + path, timeout=12) as res:
        assert res.status == 200
        return res.read().decode('utf-8')


def wait_until_ready(timeout: float = 20.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            status, payload, _ = http_json('GET', '/api/health')
            if status == 200 and payload.get('ok'):
                return payload
        except Exception:
            time.sleep(0.2)
    raise RuntimeError('server not ready')


def main():
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['NV0_DATA_DIR'] = str(DATA_DIR)
    env['NV0_ADMIN_TOKEN'] = ADMIN_TOKEN
    env['NV0_BASE_URL'] = BASE
    env['NV0_ALLOWED_HOSTS'] = '127.0.0.1,localhost,testserver'
    env['NV0_ALLOWED_ORIGINS'] = BASE
    env['NV0_BACKUP_PASSPHRASE'] = BACKUP_PASSPHRASE
    env['NV0_BOARD_ONLY_MODE'] = '0'
    env['NV0_TOSS_MOCK'] = '1'
    proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server_app:app', '--host', '127.0.0.1', '--port', str(PORT)], cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    admin_headers = {'X-Admin-Token': ADMIN_TOKEN}
    try:
        health = wait_until_ready()
        assert health['ok'] is True
        assert health['serviceMode'] == 'full'

        counts = {'orders': 0, 'demos': 0, 'contacts': 0, 'lookups': 0}
        for product in PRODUCTS:
            key = product['key']
            name = product['name']
            product_html = http_text(f'/products/{key}/')
            for needle in [name, 'id="product-demo-form"', 'name="name"', 'name="email"', 'id="product-checkout-form"']:
                assert needle in product_html, (key, needle)
            assert name in http_text(f'/products/{key}/board/')
            assert name in http_text(f'/docs/{key}/')

            demo_payload = {
                'product': key,
                'company': f'{name} Labs',
                'name': 'Kim User',
                'email': f'{key}@example.com',
                'team': '2인 운영팀',
                'need': f'{name} 데모 저장 확인',
            }
            _, demo, _ = http_json('POST', '/api/public/demo-requests', demo_payload)
            assert demo['demo']['product'] == key
            assert demo['demo']['code'].startswith('DEMO-')
            counts['demos'] += 1

            contact_payload = {
                'product': key,
                'company': f'{name} Labs',
                'email': f'contact-{key}@example.com',
                'issue': f'{name} 범위 문의',
            }
            _, contact, _ = http_json('POST', '/api/public/contact-requests', contact_payload)
            assert contact['contact']['product'] == key
            assert contact['contact']['code'].startswith('CONTACT-')
            counts['contacts'] += 1

            reserve_payload = {
                'product': key,
                'plan': 'Growth',
                'billing': 'one-time',
                'paymentMethod': 'toss',
                'company': f'{name} Labs',
                'name': 'Kim User',
                'email': f'order-{key}@example.com',
                'note': f'{name} 교차 제품 흐름 검증',
            }
            _, reserved, _ = http_json('POST', '/api/public/orders/reserve', reserve_payload)
            order = reserved['order']
            assert order['product'] == key
            assert order['paymentStatus'] == 'ready'

            _, confirmed, _ = http_json('POST', '/api/public/payments/toss/confirm', {
                'paymentKey': f'mock_{order["id"]}',
                'orderId': order['id'],
                'amount': order['amount'],
            })
            order = confirmed['order']
            assert order['product'] == key
            assert order['paymentStatus'] == 'paid'
            assert order['status'] == 'published'
            assert order['resultPack'] and order['resultPack']['outputs']
            assert order['publicationIds']
            counts['orders'] += 1

            _, lookup, _ = http_json('POST', '/api/public/portal/lookup', {
                'email': order['email'],
                'code': order['code'],
            })
            assert lookup['order']['id'] == order['id']
            assert lookup['order']['product'] == key
            assert len(lookup['publications']) >= 1
            assert all(item['product'] == key for item in lookup['publications'])
            assert all(item.get('format') == 'ai-hybrid-blog' for item in lookup['publications'])
            assert all(item.get('bodyHtml') for item in lookup['publications'])
            counts['lookups'] += 1

            _, republished, _ = http_json('POST', f'/api/admin/orders/{order["id"]}/republish', {}, headers=admin_headers)
            assert republished['order']['publicationCount'] >= len(order['publicationIds']) + 1

            _, advanced, _ = http_json('POST', f'/api/admin/orders/{order["id"]}/advance', {}, headers=admin_headers)
            assert advanced['order']['status'] == 'delivered'

        _, state_payload, _ = http_json('GET', '/api/admin/state', headers=admin_headers)
        state = state_payload['state']
        assert len(state['orders']) == counts['orders']
        assert len(state['demos']) == counts['demos']
        assert len(state['contacts']) == counts['contacts']
        assert len(state['lookups']) == counts['lookups']
        assert len(state['publications']) >= counts['orders'] * 2
        print('PRODUCT_SURFACE_E2E_OK')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        shutil.rmtree(DATA_DIR, ignore_errors=True)


if __name__ == '__main__':
    main()
