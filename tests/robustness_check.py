from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8047
BASE = f'http://127.0.0.1:{PORT}'
ADMIN_TOKEN = 'x' * 32
BACKUP = 'y' * 24


def request_json(method: str, path: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f'{BASE}{path}', data=data, method=method)
    req.add_header('Accept', 'application/json')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8'))


def spawn_server() -> tuple[subprocess.Popen, Path]:
    db_dir = Path(tempfile.mkdtemp(prefix='nv0-robust-'))
    env = os.environ.copy()
    env.update({
        'PORT': str(PORT),
        'NV0_BASE_URL': BASE,
        'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
        'NV0_BACKUP_PASSPHRASE': BACKUP,
        'NV0_TOSS_MOCK': '1',
        'NV0_DATA_DIR': str(db_dir),
        'NV0_REQUIRE_ADMIN_TOKEN': '1',
        'NV0_ENABLE_DOCS': '0',
    })
    proc = subprocess.Popen(
        ['python3', '-m', 'uvicorn', 'server_app:app', '--host', '127.0.0.1', '--port', str(PORT)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            request_json('GET', '/api/health')
            return proc, db_dir
        except Exception:
            time.sleep(0.25)
    raise RuntimeError('server did not start')


def shutdown(proc: subprocess.Popen):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_unique_codes():
    seen_orders = set()
    seen_demos = set()
    seen_contacts = set()
    for idx in range(10):
        order = request_json('POST', '/api/public/orders', {
            'product': 'veridion',
            'plan': 'Starter',
            'billing': 'one-time',
            'paymentMethod': 'manual',
            'company': f'Code Test {idx}',
            'name': 'Tester',
            'email': f'code-{idx}@example.com',
        })['order']
        demo = request_json('POST', '/api/public/demo-requests', {
            'product': 'veridion',
            'company': f'Demo {idx}',
            'name': 'Tester',
            'email': f'demo-{idx}@example.com',
        })['demo']
        contact = request_json('POST', '/api/public/contact-requests', {
            'product': 'grantops',
            'company': f'Contact {idx}',
            'email': f'contact-{idx}@example.com',
            'issue': 'Need help',
        })['contact']
        assert order['code'] not in seen_orders
        assert demo['code'] not in seen_demos
        assert contact['code'] not in seen_contacts
        seen_orders.add(order['code'])
        seen_demos.add(demo['code'])
        seen_contacts.add(contact['code'])


def test_confirm_idempotency_and_publication_dedup():
    reserve = request_json('POST', '/api/public/orders/reserve', {
        'product': 'veridion',
        'plan': 'Growth',
        'company': 'Race Co',
        'name': 'Race User',
        'email': 'race@example.com',
    })['order']
    payload = {
        'paymentKey': f'mock_{reserve["id"]}',
        'orderId': reserve['id'],
        'amount': reserve['amount'],
    }
    results = []
    errors = []

    def worker_confirm():
        try:
            results.append(request_json('POST', '/api/public/payments/toss/confirm', payload)['order'])
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker_confirm) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors
    assert results and all(item['paymentStatus'] == 'paid' for item in results)

    state = request_json('GET', '/api/admin/state', headers={'X-Admin-Token': ADMIN_TOKEN})['state']
    order = next(item for item in state['orders'] if item['id'] == reserve['id'])
    pubs = [item for item in state['publications'] if item.get('orderId') == reserve['id']]
    assert order['paymentStatus'] == 'paid'
    assert len(order['publicationIds']) == len(set(order['publicationIds'])) == len(pubs) == 2




def test_portal_lookup_email_and_code_normalization():
    reserve = request_json('POST', '/api/public/orders/reserve', {
        'product': 'draftforge',
        'plan': 'Starter',
        'company': 'Lookup Co',
        'name': 'Lookup User',
        'email': 'Lookup@Example.com',
    })['order']
    request_json('POST', '/api/public/payments/toss/confirm', {
        'paymentKey': f'mock_{reserve["id"]}',
        'orderId': reserve['id'],
        'amount': reserve['amount'],
    })
    looked = request_json('POST', '/api/public/portal/lookup', {
        'email': 'lookup@example.COM',
        'code': reserve['code'].lower(),
    })
    assert looked['order']['id'] == reserve['id']
    assert looked['order']['paymentStatus'] == 'paid'


def test_duplicate_webhook_ignored_cleanly():
    reserve = request_json('POST', '/api/public/orders/reserve', {
        'product': 'grantops',
        'plan': 'Starter',
        'company': 'Webhook Dup Co',
        'name': 'Webhook Dup User',
        'email': 'dup@example.com',
    })['order']
    webhook_payload = {
        'eventType': 'PAYMENT_STATUS_CHANGED',
        'orderId': reserve['id'],
        'data': {
            'orderId': reserve['id'],
            'paymentKey': f'mock_{reserve["id"]}',
            'status': 'DONE',
            'secret': 'dup-secret',
        },
    }
    first = request_json('POST', '/api/public/payments/toss/webhook', webhook_payload)
    second = request_json('POST', '/api/public/payments/toss/webhook', webhook_payload)
    assert first.get('ok') is True
    assert second.get('ignored') is True
    assert second.get('reason') == 'duplicate_webhook'

def test_webhook_confirm_race_safe():
    reserve = request_json('POST', '/api/public/orders/reserve', {
        'product': 'clearport',
        'plan': 'Growth',
        'company': 'Webhook Co',
        'name': 'Webhook User',
        'email': 'webhook@example.com',
    })['order']
    confirm_payload = {
        'paymentKey': f'mock_{reserve["id"]}',
        'orderId': reserve['id'],
        'amount': reserve['amount'],
    }
    webhook_payload = {
        'eventType': 'PAYMENT_STATUS_CHANGED',
        'orderId': reserve['id'],
        'data': {
            'orderId': reserve['id'],
            'paymentKey': f'mock_{reserve["id"]}',
            'status': 'DONE',
            'secret': 'race-secret',
        },
    }

    errors = []

    def call_confirm():
        try:
            request_json('POST', '/api/public/payments/toss/confirm', confirm_payload)
        except Exception as exc:
            errors.append(exc)

    def call_webhook():
        try:
            request_json('POST', '/api/public/payments/toss/webhook', webhook_payload)
        except Exception as exc:
            errors.append(exc)

    a = threading.Thread(target=call_confirm)
    b = threading.Thread(target=call_webhook)
    a.start(); b.start(); a.join(); b.join()
    assert not errors, errors

    state = request_json('GET', '/api/admin/state', headers={'X-Admin-Token': ADMIN_TOKEN})['state']
    order = next(item for item in state['orders'] if item['id'] == reserve['id'])
    pubs = [item for item in state['publications'] if item.get('orderId') == reserve['id']]
    assert order['paymentStatus'] == 'paid'
    assert len(order['publicationIds']) == len(set(order['publicationIds'])) == len(pubs) == 2


if __name__ == '__main__':
    proc, _ = spawn_server()
    try:
        test_unique_codes()
        test_confirm_idempotency_and_publication_dedup()
        test_portal_lookup_email_and_code_normalization()
        test_duplicate_webhook_ignored_cleanly()
        test_webhook_confirm_race_safe()
        print('ROBUSTNESS_OK', flush=True)
    finally:
        shutdown(proc)
