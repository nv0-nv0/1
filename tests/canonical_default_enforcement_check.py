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
            with urlopen(req, timeout=15) as res:
                return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
        with opener.open(req, timeout=15) as res:  # type: ignore[arg-type]
            return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
    except HTTPError as exc:
        return exc.code, exc.read(), {str(k).lower(): str(v) for k, v in exc.headers.items()}


def wait_ready(base_url: str, *, canonical_host: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            status, body, _ = fetch(base_url, '/api/health', host=canonical_host)
            if status == 200 and json.loads(body.decode('utf-8')).get('ok') is True:
                return
        except Exception as exc:
            last = exc
        time.sleep(0.25)
    raise RuntimeError(f'server not ready: {last}')


def main() -> None:
    port = free_port()
    data_dir = Path(tempfile.mkdtemp(prefix='nv0-canonical-auto-'))
    canonical_host = 'nv0.kr'
    env = os.environ.copy()
    env.update({
        'PORT': str(port),
        'NV0_DATA_DIR': str(data_dir),
        'NV0_BASE_URL': f'https://{canonical_host}',
        'NV0_ALLOWED_HOSTS': canonical_host,
        'NV0_INTERNAL_HOSTS': '127.0.0.1,localhost,nv0-company',
        'NV0_ALLOWED_ORIGINS': f'https://{canonical_host}',
        'NV0_ADMIN_TOKEN': 'canonical-auto-admin-token-abcdefghijklmnopqrstuvwxyz-123456',
        'NV0_BACKUP_PASSPHRASE': 'canonical-auto-backup-passphrase-abcdefghijklmnopqrstuvwxyz',
        'NV0_REQUIRE_ADMIN_TOKEN': '1',
        'NV0_TOSS_MOCK': '1',
    })
    env.pop('NV0_ENFORCE_CANONICAL_HOST', None)
    env.pop('NV0_CANONICAL_HOST', None)
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
        wait_ready(base_url, canonical_host=canonical_host)
        status, _, headers = fetch(base_url, '/api/health', host='wrong.example', follow_redirects=False)
        if status != 308:
            raise AssertionError(f'expected 308 redirect, got {status}')
        location = headers.get('location', '')
        expected = f'https://{canonical_host}/api/health'
        if location != expected:
            raise AssertionError(f'expected {expected!r}, got {location!r}')
        print('CANONICAL_DEFAULT_ENFORCEMENT_OK')
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
