from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_HOST = 'nv0.kr'
INTERNAL_HOST = 'nv0-company'
ADMIN_TOKEN = 'healthcheck-surface-admin-token-abcdefghijklmnopqrstuvwxyz'
BACKUP_PASSPHRASE = 'healthcheck-backup-passphrase-abcdefghijklmnopqrstuvwxyz'


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT = build_opener(NoRedirectHandler)


def free_port() -> int:
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def fetch(base_url: str, path: str, *, host: str, follow_redirects: bool = True):
    req = Request(base_url + path, method='GET')
    req.add_unredirected_header('Host', host)
    opener = None if follow_redirects else NO_REDIRECT
    try:
        if opener is None:
            with urlopen(req, timeout=10) as res:
                return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
        with opener.open(req, timeout=10) as res:  # type: ignore[arg-type]
            return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
    except HTTPError as exc:
        return exc.code, exc.read(), {str(k).lower(): str(v) for k, v in exc.headers.items()}


def wait_ready(base_url: str, *, host: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, body, _ = fetch(base_url, '/readyz', host=host)
            if status == 200 and json.loads(body.decode('utf-8')).get('ok') is True:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f'server not ready: {last_error}')


def main() -> None:
    port = free_port()
    data_dir = Path(tempfile.mkdtemp(prefix='nv0-health-surface-'))
    env = os.environ.copy()
    env.update({
        'PORT': str(port),
        'NV0_DATA_DIR': str(data_dir),
        'NV0_BASE_URL': f'https://{CANONICAL_HOST}',
        'NV0_ALLOWED_HOSTS': CANONICAL_HOST,
        'NV0_INTERNAL_HOSTS': f'127.0.0.1,localhost,{INTERNAL_HOST}',
        'NV0_ALLOWED_ORIGINS': f'https://{CANONICAL_HOST}',
        'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
        'NV0_BACKUP_PASSPHRASE': BACKUP_PASSPHRASE,
        'NV0_REQUIRE_ADMIN_TOKEN': '1',
        'NV0_TOSS_MOCK': '1',
        'NV0_CANONICAL_HOST': CANONICAL_HOST,
        'NV0_ENFORCE_CANONICAL_HOST': '1',
        'NV0_CANONICAL_SCHEME': 'https',
    })
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'server_app:app', '--host', '127.0.0.1', '--port', str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base_url = f'http://127.0.0.1:{port}'
        wait_ready(base_url, host='127.0.0.1')

        for path in ('/health', '/healthz', '/live', '/livez', '/ready', '/readyz', '/api/health'):
            status, body, _ = fetch(base_url, path, host='127.0.0.1')
            if status != 200:
                raise AssertionError(f'{path} expected 200, got {status}')
            payload = json.loads(body.decode('utf-8'))
            if payload.get('ok') is not True:
                raise AssertionError(f'{path} ok=false')
        status, body, _ = fetch(base_url, '/readyz', host=INTERNAL_HOST)
        if status != 200:
            raise AssertionError(f'internal host /readyz expected 200, got {status}')
        payload = json.loads(body.decode('utf-8'))
        if payload.get('checks', {}).get('dbQuery') is not True:
            raise AssertionError('readiness payload missing dbQuery=true')

        status, _, headers = fetch(base_url, '/readyz', host='wrong.example', follow_redirects=False)
        if status != 308:
            raise AssertionError(f'wrong host expected 308, got {status}')
        expected = f'https://{CANONICAL_HOST}/readyz'
        if headers.get('location') != expected:
            raise AssertionError(f'redirect mismatch: {headers.get("location")!r} != {expected!r}')

        print('HEALTHCHECK_SURFACE_OK')
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
