from __future__ import annotations

import importlib
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / 'requirements.txt'
VENV_DIR = ROOT / '.venvcheck'


def free_port() -> int:
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def ensure_venv() -> Path:
    try:
        importlib.import_module('fastapi')
        importlib.import_module('uvicorn')
        return Path(sys.executable)
    except Exception:
        pass
    python_bin = VENV_DIR / 'bin' / 'python'
    marker = VENV_DIR / '.requirements.sha256'
    req_hash = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if not python_bin.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(VENV_DIR)], check=True, cwd=str(ROOT))
    subprocess.run([str(python_bin), '-m', 'ensurepip', '--upgrade'], check=True, cwd=str(ROOT))
    if marker.read_text(encoding='utf-8').strip() != req_hash if marker.exists() else True:
        subprocess.run([str(python_bin), '-m', 'pip', 'install', '-q', '-r', str(REQUIREMENTS)], check=True, cwd=str(ROOT))
        marker.write_text(req_hash, encoding='utf-8')
    return python_bin


def wait_ready(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + '/api/health', timeout=3) as res:
                if res.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.3)
    raise RuntimeError(f'health timeout: {last_error}')


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as res:
        return json.loads(res.read().decode('utf-8'))


def start_server(repo_root: Path, python_bin: Path, *, port: int, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env.update({
        'PORT': str(port),
        'NV0_ALLOWED_HOSTS': '127.0.0.1,localhost',
        'NV0_ALLOWED_ORIGINS': f'http://127.0.0.1:{port}',
        'NV0_ADMIN_TOKEN': 'packaging-runtime-token-abcdefghijklmnopqrstuvwxyz',
        'NV0_BACKUP_PASSPHRASE': 'packaging-backup-passphrase-abcdefghijklmnopqrstuvwxyz',
        'NV0_DATA_DIR': tempfile.mkdtemp(prefix='nv0-data-'),
        'NV0_BOARD_ONLY_MODE': '0',
        'NV0_TOSS_MOCK': '1',
    })
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        [str(python_bin), '-m', 'uvicorn', 'server_app:app', '--host', '127.0.0.1', '--port', str(port)],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_server(proc: subprocess.Popen) -> str:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    return proc.stdout.read() if proc.stdout else ''


def assert_port_derived_base_url(python_bin: Path) -> None:
    port = free_port()
    proc = start_server(ROOT, python_bin, port=port)
    base = f'http://127.0.0.1:{port}'
    try:
        wait_ready(base)
        payload = fetch_json(base + '/api/public/system-config')
        config = payload['config']
        assert config['boardOnly'] is False
        assert config['payment']['provider'] == 'toss'
        assert config['payment']['toss']['mock'] is True
        assert config['payment']['toss']['successUrl'] == base + '/payments/toss/success/'
        assert config['payment']['toss']['failUrl'] == base + '/payments/toss/fail/'
    finally:
        output = stop_server(proc)
        if proc.returncode not in (0, -15):
            raise RuntimeError(f'uvicorn runtime check failed\n{output}')


def copy_repo_without_runtime_artifacts(target: Path) -> Path:
    repo_copy = target / 'repo'
    shutil.copytree(ROOT, repo_copy, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
        '.venvcheck', '__pycache__', '.testdata', '.testdata_full', '*.pyc', 'AUDIT_REPORT_KO.md'
    ))
    shutil.rmtree(repo_copy / 'dist', ignore_errors=True)
    return repo_copy


def assert_startup_autobuild(python_bin: Path) -> None:
    with tempfile.TemporaryDirectory(prefix='nv0-autobuild-') as tmp:
        repo_copy = copy_repo_without_runtime_artifacts(Path(tmp))
        port = free_port()
        proc = start_server(repo_copy, python_bin, port=port)
        base = f'http://127.0.0.1:{port}'
        try:
            wait_ready(base)
            dist_index = repo_copy / 'dist' / 'products' / 'veridion' / 'index.html'
            if not dist_index.exists():
                raise RuntimeError('startup auto-build did not create full product page')
            with urllib.request.urlopen(base + '/products/veridion/', timeout=5) as res:
                if res.status != 200:
                    raise RuntimeError(f'product page status {res.status}')
        finally:
            output = stop_server(proc)
            if proc.returncode not in (0, -15):
                raise RuntimeError(f'uvicorn autobuild check failed\n{output}')


def main() -> None:
    python_bin = ensure_venv()
    assert_port_derived_base_url(python_bin)
    assert_startup_autobuild(python_bin)
    print('PACKAGING_RUNTIME_OK')


if __name__ == '__main__':
    main()
