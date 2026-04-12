from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PORT = 8044
BASE = f'http://127.0.0.1:{PORT}'
DATA_DIR = ROOT / '.testdata_full'
ADMIN_TOKEN = 'admin-test-token-abcdefghijklmnopqrstuvwxyz1234'
BACKUP_PASSPHRASE = 'test-backup-passphrase-1234567890-abcdef'


def http_json(method: str, path: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE + path, data=data, method=method)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=10) as res:
        body = res.read().decode('utf-8')
        return res.status, json.loads(body) if body else None, dict(res.headers)


def http_text(path: str) -> str:
    with urlopen(BASE + path, timeout=10) as res:
        assert res.status == 200
        return res.read().decode('utf-8')


def http_error_json(method: str, path: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE + path, data=data, method=method)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=10) as res:
            body = res.read().decode('utf-8')
            return res.status, json.loads(body) if body else None, dict(res.headers)
    except HTTPError as err:
        body = err.read().decode('utf-8')
        parsed = json.loads(body) if body else None
        return err.code, parsed, dict(err.headers)


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
        assert health['payment']['provider'] == 'toss'
        assert health['payment']['tossMock'] is True

        _, system_cfg, _ = http_json('GET', '/api/public/system-config')
        config = system_cfg['config']
        assert config['boardOnly'] is False
        assert config['payment']['provider'] == 'toss'
        assert config['payment']['toss']['mock'] is True
        assert config['payment']['toss']['successUrl'].endswith('/payments/toss/success/')
        assert config['payment']['toss']['failUrl'].endswith('/payments/toss/fail/')

        veridion = http_text('/products/veridion/')
        for needle in ['id="product-demo-form"', 'id="product-checkout-form"', 'id="product-board-grid"', '#payment', '#delivery']:
            assert needle in veridion, needle
        for page in ['/products/', '/checkout/', '/portal/', '/pricing/', '/docs/', '/cases/', '/faq/', '/demo/', '/contact/', '/payments/toss/success/']:
            http_text(page)

        reserve_payload = {
            'product': 'veridion',
            'plan': 'Growth',
            'billing': 'one-time',
            'paymentMethod': 'toss',
            'company': 'Acme Labs',
            'name': 'Kim User',
            'email': 'kim@example.com',
            'note': '즉시 시연 후 구매',
        }
        _, reserved, _ = http_json('POST', '/api/public/orders/reserve', reserve_payload)
        order = reserved['order']
        assert order['paymentStatus'] == 'ready'
        assert order['status'] == 'payment_pending'
        assert reserved['payment']['mock'] is True
        assert order['amount'] > 0

        _, confirmed, _ = http_json('POST', '/api/public/payments/toss/confirm', {
            'paymentKey': 'mock_test_payment',
            'orderId': order['id'],
            'amount': order['amount'],
        })
        order = confirmed['order']
        assert order['paymentStatus'] == 'paid'
        assert order['status'] == 'published'
        assert len(order['publicationIds']) >= 1
        assert order['resultPack'] and order['resultPack']['outputs']

        _, board_feed, _ = http_json('GET', '/api/public/board/feed')
        first_pub = board_feed['items'][0]
        assert first_pub['format'] == 'ai-hybrid-blog'
        assert first_pub['bodyHtml']
        assert first_pub['sections'] and len(first_pub['sections']) >= 4
        assert first_pub['keywords']

        _, lookup, _ = http_json('POST', '/api/public/portal/lookup', {
            'email': order['email'],
            'code': order['code'],
        })
        assert lookup['order']['id'] == order['id']
        assert len(lookup['publications']) >= 1
        status, bad_lookup, _ = http_error_json('POST', '/api/public/portal/lookup', {
            'email': order['email'],
            'code': '',
        })
        assert status == 400
        assert '조회 코드' in bad_lookup['detail']

        _, demo, _ = http_json('POST', '/api/public/demo-requests', {
            'product': 'veridion',
            'company': 'Acme Labs',
            'name': 'Kim User',
            'email': 'kim@example.com',
            'team': '3인',
            'need': '랜딩 구조 미리 보기',
            'keywords': '랜딩, CTA, 신뢰',
            'plan': 'Growth',
        })
        assert demo['demo']['code'].startswith('DEMO-VER-')
        assert demo['demo']['keywords'] == '랜딩, CTA, 신뢰'
        assert demo['demo']['plan'] == 'Growth'

        _, contact, _ = http_json('POST', '/api/public/contact-requests', {
            'product': 'grantops',
            'company': 'Acme Labs',
            'name': 'Kim User',
            'email': 'kim@example.com',
            'issue': '납품 범위 문의',
        })
        assert contact['contact']['code'].startswith('CONTACT-GRT-')
        assert contact['contact']['name'] == 'Kim User'

        _, seeded, _ = http_json('POST', '/api/admin/actions/seed-demo', {}, headers=admin_headers)
        seeded_order = seeded['order']
        assert seeded_order['product'] == 'veridion'

        _, republished, _ = http_json('POST', f"/api/admin/orders/{order['id']}/republish", {}, headers=admin_headers)
        assert republished['order']['publicationCount'] >= len(order['publicationIds'])

        _, advanced, _ = http_json('POST', f"/api/admin/orders/{order['id']}/advance", {}, headers=admin_headers)
        assert advanced['order']['status'] == 'delivered'

        _, toggled, _ = http_json('POST', f"/api/admin/orders/{seeded_order['id']}/toggle-payment", {}, headers=admin_headers)
        assert toggled['order']['paymentStatus'] in {'pending', 'paid'}

        print('FULL_API_E2E_OK')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == '__main__':
    main()
