from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VENDOR = ROOT / 'runtime_vendor'


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    merged = os.environ.copy()
    merged['PYTHONPATH'] = str(RUNTIME_VENDOR)
    if env:
        merged.update(env)
    print('$', ' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), env=merged, check=True)


def wait_health(base_url: str, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    last_error: str | None = None
    while time.time() < deadline:
        try:
            with urlopen(base_url.rstrip('/') + '/api/health', timeout=2) as res:
                payload = json.loads(res.read().decode('utf-8'))
                if payload.get('ok') is True:
                    return
        except Exception as exc:  # pragma: no cover - runtime utility
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f'health check timeout for {base_url}: {last_error or "unknown error"}')


def start_server(mode: str, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env['PYTHONPATH'] = str(RUNTIME_VENDOR)
    env['PORT'] = str(port)
    env['NV0_BASE_URL'] = f'http://127.0.0.1:{port}'
    env['NV0_ALLOWED_HOSTS'] = '127.0.0.1,localhost'
    env['NV0_ALLOWED_ORIGINS'] = f'http://127.0.0.1:{port}'
    env['NV0_ADMIN_TOKEN'] = 'nv0-local-admin-token-1234567890'
    env['NV0_BACKUP_PASSPHRASE'] = 'nv0-local-backup-passphrase-1234567890'
    env['NV0_ENABLE_DOCS'] = '0'
    env['FORWARDED_ALLOW_IPS'] = '127.0.0.1'
    env['NV0_TOSS_MOCK'] = '1'
    env['NV0_BOARD_ONLY_MODE'] = '1' if mode == 'board' else '0'
    proc = subprocess.Popen(
        [sys.executable, 'start_server.py'],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    wait_health(env['NV0_BASE_URL'])
    return proc


def stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def verify_mode(mode: str, port: int) -> None:
    env = {
        'NV0_BASE_URL': f'http://127.0.0.1:{port}',
        'NV0_ALLOWED_HOSTS': '127.0.0.1,localhost',
        'NV0_ALLOWED_ORIGINS': f'http://127.0.0.1:{port}',
        'NV0_ADMIN_TOKEN': 'nv0-local-admin-token-1234567890',
        'NV0_BACKUP_PASSPHRASE': 'nv0-local-backup-passphrase-1234567890',
        'NV0_TOSS_MOCK': '1',
        'FORWARDED_ALLOW_IPS': '127.0.0.1',
        'NV0_BOARD_ONLY_MODE': '1' if mode == 'board' else '0',
    }
    run([sys.executable, 'scripts/preflight_env.py'], env=env)
    run([sys.executable, 'scripts/smoke_release.py', '--base-url', env['NV0_BASE_URL'], '--mode', mode, '--admin-token', env['NV0_ADMIN_TOKEN']], env=env)
    if mode == 'full':
        run([sys.executable, 'scripts/post_deploy_verify.py', '--base-url', env['NV0_BASE_URL'], '--admin-token', env['NV0_ADMIN_TOKEN'], '--skip-www-redirect'], env=env)
        run([sys.executable, 'scripts/product_runtime_e2e.py', '--base-url', env['NV0_BASE_URL']], env=env)
        run([sys.executable, 'scripts/result_quality_gate.py', '--base-url', env['NV0_BASE_URL']], env=env)
        run([sys.executable, 'scripts/api_safety_regression.py', '--base-url', env['NV0_BASE_URL'], '--admin-token', env['NV0_ADMIN_TOKEN']], env=env)
        run([sys.executable, 'scripts/deployment_consistency_check.py'], env=env)
    if mode == 'board':
        run([sys.executable, 'scripts/board_mode_regression.py', '--base-url', env['NV0_BASE_URL'], '--admin-token', env['NV0_ADMIN_TOKEN']], env=env)
    run([sys.executable, 'scripts/full_audit.py', '--mode', mode], env=env)


def main() -> int:
    run([sys.executable, '-m', 'py_compile', 'build.py', 'server_app.py', 'start_server.py'] + [str(p) for p in sorted((ROOT / 'scripts').glob('*.py'))])
    run(['node', '--check', 'src/assets/site.js'])

    run([sys.executable, 'build.py'], env={'NV0_BOARD_ONLY_MODE': '0'})
    full_proc = start_server('full', 8010)
    try:
        verify_mode('full', 8010)
    finally:
        stop_server(full_proc)

    run([sys.executable, 'build.py'], env={'NV0_BOARD_ONLY_MODE': '1'})
    board_proc = start_server('board', 8011)
    try:
        verify_mode('board', 8011)
    finally:
        stop_server(board_proc)

    run([sys.executable, 'build.py'], env={'NV0_BOARD_ONLY_MODE': '0'})
    print('PACKAGE_COMPLETION_GATE_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
