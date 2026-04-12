from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ADMIN_TOKEN = 'smoke-admin-token-abcdefghijklmnopqrstuvwxyz1234'
BACKUP_PASSPHRASE = 'smoke-backup-passphrase-abcdefghijklmnopqrstuvwxyz'


def free_port() -> int:
    import socket
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def wait_ready(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(base_url + '/api/health', timeout=3) as res:
                if res.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError('smoke server not ready')


def start_server(board_only: bool) -> tuple[subprocess.Popen, str, Path]:
    port = free_port()
    data_dir = Path(tempfile.mkdtemp(prefix='nv0-smoke-data-'))
    env = os.environ.copy()
    env.update({
        'NV0_DATA_DIR': str(data_dir),
        'NV0_BASE_URL': f'http://127.0.0.1:{port}',
        'NV0_ALLOWED_HOSTS': '127.0.0.1,localhost',
        'NV0_ALLOWED_ORIGINS': f'http://127.0.0.1:{port}',
        'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
        'NV0_BACKUP_PASSPHRASE': BACKUP_PASSPHRASE,
        'NV0_BOARD_ONLY_MODE': '1' if board_only else '0',
        'NV0_TOSS_MOCK': '1',
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


def stop_server(proc: subprocess.Popen, data_dir: Path) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    shutil.rmtree(data_dir, ignore_errors=True)


def run_smoke(board_only: bool) -> None:
    proc, base_url, data_dir = start_server(board_only)
    try:
        wait_ready(base_url)
        mode = 'board' if board_only else 'full'
        subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'smoke_release.py'), '--base-url', base_url, '--mode', mode, '--admin-token', ADMIN_TOKEN],
            cwd=str(ROOT),
            check=True,
            timeout=240,
        )
    finally:
        stop_server(proc, data_dir)


def main() -> None:
    run_smoke(board_only=False)
    run_smoke(board_only=True)
    print('RELEASE_SMOKE_OK')


if __name__ == '__main__':
    main()
