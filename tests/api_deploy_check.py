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
PORT = 8043
BASE = f'http://127.0.0.1:{PORT}'
DATA_DIR = ROOT / '.testdata'
ADMIN_TOKEN = 'admin-test-token-abcdefghijklmnopqrstuvwxyz1234'
BACKUP_PASSPHRASE = 'test-backup-passphrase-1234567890-abcdef'


def http_json(method: str, path: str, payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE + path, data=data, method=method)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urlopen(req, timeout=8) as res:
        body = res.read().decode('utf-8')
        return res.status, json.loads(body) if body else None, dict(res.headers)


def expect_http_error(method: str, path: str, payload: dict | None = None, headers: dict | None = None, status_code: int = 400):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE + path, data=data, method=method)
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        urlopen(req, timeout=8)
    except HTTPError as exc:
        assert exc.code == status_code
        body = exc.read().decode('utf-8')
        return json.loads(body) if body.startswith('{') else {'detail': body}
    raise AssertionError(f'{path} should fail with {status_code}')


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
    env['NV0_BASE_URL'] = 'https://nv0.test'
    env['NV0_ALLOWED_HOSTS'] = '127.0.0.1,localhost,testserver'
    env['NV0_ALLOWED_ORIGINS'] = BASE
    env['NV0_BACKUP_PASSPHRASE'] = BACKUP_PASSPHRASE
    env['NV0_BOARD_ONLY_MODE'] = '1'
    proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server_app:app', '--host', '127.0.0.1', '--port', str(PORT)], cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    admin_headers = {'X-Admin-Token': ADMIN_TOKEN}
    try:
        health = wait_until_ready()
        assert health['ok'] is True
        assert health['serviceMode'] == 'board_only'

        _, system_cfg, _ = http_json('GET', '/api/public/system-config')
        assert system_cfg['config']['boardOnly'] is True
        assert 'orders' in system_cfg['config']['disabledFeatures']
        assert system_cfg['config']['payment']['provider'] == 'disabled'
        assert system_cfg['config']['payment']['toss']['enabled'] is False

        _, board_feed_seed, _ = http_json('GET', '/api/public/board/feed')
        assert len(board_feed_seed['items']) >= 8

        disabled = [
            '/api/public/orders',
            '/api/public/orders/reserve',
            '/api/public/payments/toss/confirm',
            '/api/public/payments/toss/webhook',
            '/api/public/demo-requests',
            '/api/public/contact-requests',
            '/api/public/portal/lookup',
        ]
        for path in disabled:
            err = expect_http_error('POST', path, {}, status_code=410)
            assert err['mode'] == 'board_only'


        for path in ['/pricing/', '/products/', '/demo/', '/checkout/', '/contact/', '/portal/']:
            req = Request(BASE + path, method='GET')
            try:
                urlopen(req, timeout=8)
                raise AssertionError(f'{path} should fail with 410')
            except HTTPError as exc:
                assert exc.code == 410
                body = exc.read().decode('utf-8')
                assert 'CTA 포스팅 자동발행 게시판만 운영합니다' in body

        _, state_before, _ = http_json('GET', '/api/admin/state', headers=admin_headers)
        before_count = len(state_before['state']['publications'])

        _, publish_now, _ = http_json('POST', '/api/admin/actions/publish-now', {}, headers=admin_headers)
        assert publish_now['ok'] is True
        assert len(publish_now['published']) >= 1

        _, state_after_publish, _ = http_json('GET', '/api/admin/state', headers=admin_headers)
        after_count = len(state_after_publish['state']['publications'])
        assert after_count > before_count

        _, reseed, _ = http_json('POST', '/api/admin/actions/reseed-board', {}, headers=admin_headers)
        assert reseed['ok'] is True
        assert len(reseed['state']['publications']) >= 8

        backup_dir = DATA_DIR / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_env = env.copy()
        backup_env['NV0_BACKUP_DIR'] = str(backup_dir)
        subprocess.run([sys.executable, 'scripts/backup_state.py', '--base-url', BASE, '--output-dir', str(backup_dir), '--retention', '3'], cwd=str(ROOT), env=backup_env, check=True)
        backups = sorted(backup_dir.glob('*.enc')) + sorted(backup_dir.glob('*.tar.gz.enc'))
        assert backups, 'encrypted backup not created'
        subprocess.run([sys.executable, 'scripts/restore_state.py', str(backups[-1]), '--verify-only'], cwd=str(ROOT), env=backup_env, check=True)

        print('API_DEPLOY_OK')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == '__main__':
    main()
