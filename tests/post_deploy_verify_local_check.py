from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_TOKEN = 'post-deploy-local-check-admin-token-abcdefghijklmnopqrstuvwxyz'
BACKUP_PASSPHRASE = 'post-deploy-local-check-passphrase-abcdefghijklmnopqrstuvwxyz'


def free_port() -> int:
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def start_server() -> tuple[subprocess.Popen[str], str, Path]:
    port = free_port()
    data_dir = Path(tempfile.mkdtemp(prefix='nv0-postdeploy-data-'))
    env = os.environ.copy()
    env.update({
        'PORT': str(port),
        'NV0_DATA_DIR': str(data_dir),
        'NV0_BASE_URL': f'http://127.0.0.1:{port}',
        'NV0_ALLOWED_HOSTS': '127.0.0.1,localhost',
        'NV0_ALLOWED_ORIGINS': f'http://127.0.0.1:{port}',
        'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
        'NV0_BACKUP_PASSPHRASE': BACKUP_PASSPHRASE,
        'NV0_TOSS_MOCK': '1',
        'NV0_REQUIRE_ADMIN_TOKEN': '1',
        'NV0_ENFORCE_CANONICAL_HOST': '0',
    })
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'server_app:app', '--host', '127.0.0.1', '--port', str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, f'http://127.0.0.1:{port}', data_dir


def stop_server(proc: subprocess.Popen[str], data_dir: Path) -> str:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    output = proc.stdout.read() if proc.stdout else ''
    shutil.rmtree(data_dir, ignore_errors=True)
    return output


def wait_ready(base_url: str, timeout: float = 20.0) -> None:
    import urllib.request
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + '/api/health', timeout=5) as res:
                if res.status == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f'server not ready: {last_error}')


def main() -> int:
    proc, base_url, data_dir = start_server()
    try:
        wait_ready(base_url)
        result = subprocess.run([
            sys.executable,
            str(ROOT / 'scripts' / 'post_deploy_verify.py'),
            '--base-url', base_url,
            '--admin-token', ADMIN_TOKEN,
            '--skip-www-redirect',
        ], cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise AssertionError(f'post_deploy_verify failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}')
        if 'POST_DEPLOY_VERIFY_OK' not in result.stdout:
            raise AssertionError(f'post_deploy_verify success marker missing\nSTDOUT:\n{result.stdout}')
        print('POST_DEPLOY_VERIFY_LOCAL_OK')
        return 0
    finally:
        output = stop_server(proc, data_dir)
        if proc.returncode not in (0, -15, None):
            raise RuntimeError(f'server exited unexpectedly: {proc.returncode}\n{output}')


if __name__ == '__main__':
    raise SystemExit(main())
