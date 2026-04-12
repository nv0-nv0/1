from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]
ADMIN_TOKEN = 'quality-admin-token-abcdefghijklmnopqrstuvwxyz'
BACKUP_PASSPHRASE = 'quality-backup-passphrase-abcdefghijklmnopqrstuvwxyz'
CANONICAL_HOST = 'nv0.test'
class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT = build_opener(NoRedirectHandler)
STORE_KEYS = ('orders', 'demos', 'contacts', 'lookups', 'publications', 'webhook_events', 'scheduler')


def free_port() -> int:
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def start_server(*, board_only: bool = False) -> tuple[subprocess.Popen[str], str, Path]:
    port = free_port()
    data_dir = Path(tempfile.mkdtemp(prefix='nv0-quality-data-'))
    env = os.environ.copy()
    env.update({
        'PORT': str(port),
        'NV0_DATA_DIR': str(data_dir),
        'NV0_BASE_URL': f'http://127.0.0.1:{port}',
        'NV0_ALLOWED_HOSTS': f'127.0.0.1,localhost,{CANONICAL_HOST}',
        'NV0_ALLOWED_ORIGINS': f'http://127.0.0.1:{port}',
        'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
        'NV0_BACKUP_PASSPHRASE': BACKUP_PASSPHRASE,
        'NV0_TOSS_MOCK': '1',
        'NV0_REQUIRE_ADMIN_TOKEN': '1',
        'NV0_ENABLE_DOCS': '0',
        'NV0_ENFORCE_CANONICAL_HOST': '1',
        'NV0_CANONICAL_HOST': CANONICAL_HOST,
        'NV0_CANONICAL_SCHEME': 'https',
        'NV0_BOARD_ONLY_MODE': '1' if board_only else '0',
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


def fetch(method: str, base_url: str, path: str, payload: dict | None = None, *, headers: dict[str, str] | None = None, follow_redirects: bool = True) -> tuple[int, bytes, dict[str, str]]:
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(base_url + path, data=data, method=method)
    merged_headers = {'Host': CANONICAL_HOST, **(headers or {})}
    host_value = merged_headers.pop('Host', CANONICAL_HOST)
    req.add_unredirected_header('Host', host_value)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in merged_headers.items():
        req.add_header(key, value)
    opener = None if follow_redirects else NO_REDIRECT
    try:
        if opener is None:
            with urlopen(req, timeout=15) as res:
                return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
        with opener.open(req, timeout=15) as res:  # type: ignore[arg-type]
            return res.status, res.read(), {str(k).lower(): str(v) for k, v in res.headers.items()}
    except HTTPError as exc:
        return exc.code, exc.read(), {str(k).lower(): str(v) for k, v in exc.headers.items()}


def wait_ready(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, body, _ = fetch('GET', base_url, '/api/health')
            if status == 200 and json.loads(body.decode('utf-8')).get('ok') is True:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f'server not ready: {last_error}')


def assert_header_contains(headers: dict[str, str], key: str, expected: str, *, path: str) -> None:
    actual = headers.get(key.lower(), '')
    if expected not in actual:
        raise AssertionError(f'{path} header {key} missing {expected!r}: {actual!r}')


def assert_security_headers(base_url: str) -> None:
    sensitive_html = ['/admin/', '/portal/', '/checkout/', '/payments/toss/success/']
    for path in ['/', '/api/health', '/does-not-exist', '/assets/site.js', *sensitive_html]:
        status, _, headers = fetch('GET', base_url, path, headers={'X-Admin-Token': ADMIN_TOKEN})
        if path == '/does-not-exist':
            assert status == 404, status
        else:
            assert status == 200, (path, status)
        assert_header_contains(headers, 'Content-Security-Policy', "default-src 'self'", path=path)
        assert_header_contains(headers, 'X-Content-Type-Options', 'nosniff', path=path)
        assert_header_contains(headers, 'X-Frame-Options', 'SAMEORIGIN', path=path)
    for path in sensitive_html:
        _, _, headers = fetch('GET', base_url, path, headers={'X-Admin-Token': ADMIN_TOKEN})
        assert_header_contains(headers, 'Cache-Control', 'no-store', path=path)
        assert_header_contains(headers, 'X-Robots-Tag', 'noindex, nofollow', path=path)
    _, _, asset_headers = fetch('GET', base_url, '/assets/site.js')
    assert_header_contains(asset_headers, 'Cache-Control', 'immutable', path='/assets/site.js')
    status, _, headers = fetch('GET', base_url, '/api/health', follow_redirects=False, headers={'Host': 'wrong.example'})
    assert status == 308, status
    location = headers.get('location', '')
    if location != f'https://{CANONICAL_HOST}/api/health':
        raise AssertionError(f'canonical redirect mismatch: {location!r}')


def create_paid_order(base_url: str) -> dict:
    _, _, _ = fetch('POST', base_url, '/api/public/demo-requests', {
        'product': 'veridion',
        'company': 'Quality Labs',
        'name': 'Quality User',
        'email': 'quality@example.com',
        'team': '1인',
        'need': '품질 확인',
    })
    _, _, _ = fetch('POST', base_url, '/api/public/contact-requests', {
        'product': 'grantops',
        'company': 'Quality Labs',
        'email': 'quality@example.com',
        'issue': '품질 확인 문의',
    })
    _, reserve_body, _ = fetch('POST', base_url, '/api/public/orders/reserve', {
        'product': 'veridion',
        'plan': 'Starter',
        'billing': 'one-time',
        'paymentMethod': 'toss',
        'company': 'Quality Labs',
        'name': 'Quality User',
        'email': 'quality@example.com',
        'note': 'quality-check',
    })
    reserve = json.loads(reserve_body.decode('utf-8'))['order']
    _, confirm_body, _ = fetch('POST', base_url, '/api/public/payments/toss/confirm', {
        'paymentKey': f'mock_{reserve["id"]}',
        'orderId': reserve['id'],
        'amount': reserve['amount'],
    })
    return json.loads(confirm_body.decode('utf-8'))['order']


def fetch_state(base_url: str) -> dict:
    _, body, _ = fetch('GET', base_url, '/api/admin/state', headers={'X-Admin-Token': ADMIN_TOKEN})
    return json.loads(body.decode('utf-8'))['state']


def record_counts(state: dict) -> dict[str, int]:
    return {key: len(state.get(key, []) or []) for key in STORE_KEYS}


def assert_backup_restore_roundtrip(base_url: str) -> None:
    restored_proc = None
    restored_data_dir = None
    try:
        order = create_paid_order(base_url)
        _status, _body, _headers = fetch('POST', base_url, '/api/public/portal/lookup', {
            'email': order['email'],
            'code': order['code'],
        })
        expected = record_counts(fetch_state(base_url))
        backup_dir = Path(tempfile.mkdtemp(prefix='nv0-quality-backups-'))
        env = os.environ.copy()
        env.update({
            'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
            'NV0_BACKUP_PASSPHRASE': BACKUP_PASSPHRASE,
            'NV0_BACKUP_DIR': str(backup_dir),
            'NV0_BASE_URL': base_url,
        })
        subprocess.run([
            sys.executable, str(ROOT / 'scripts' / 'backup_state.py'), '--base-url', base_url, '--output-dir', str(backup_dir), '--retention', '2'
        ], cwd=str(ROOT), env=env, check=True, timeout=120)
        backups = sorted(backup_dir.glob('*.enc')) + sorted(backup_dir.glob('*.tar.gz.enc'))
        if not backups:
            raise AssertionError('backup not created')
        restored_proc, restored_base, restored_data_dir = start_server(board_only=False)
        wait_ready(restored_base)
        restore_env = os.environ.copy()
        restore_env.update({
            'NV0_ADMIN_TOKEN': ADMIN_TOKEN,
            'NV0_BACKUP_PASSPHRASE': BACKUP_PASSPHRASE,
            'NV0_BASE_URL': restored_base,
        })
        subprocess.run([
            sys.executable, str(ROOT / 'scripts' / 'restore_state.py'), str(backups[-1]), '--base-url', restored_base
        ], cwd=str(ROOT), env=restore_env, check=True, timeout=120)
        restored = record_counts(fetch_state(restored_base))
        if restored != expected:
            raise AssertionError(f'restored state mismatch: expected {expected}, got {restored}')
    finally:
        if restored_proc is not None and restored_data_dir is not None:
            output = stop_server(restored_proc, restored_data_dir)
            if restored_proc.returncode not in (0, -15):
                raise RuntimeError(f'restored server failed\n{output}')


def timed_request(base_url: str, path: str) -> float:
    started = time.perf_counter()
    status, _, _ = fetch('GET', base_url, path, headers={'X-Admin-Token': ADMIN_TOKEN})
    if status != 200:
        raise AssertionError(f'{path} status {status}')
    return time.perf_counter() - started


def assert_performance(base_url: str) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for path in ('/api/public/board/feed', '/api/admin/state'):
        seq = [timed_request(base_url, path) for _ in range(20)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            conc = list(ex.map(lambda _: timed_request(base_url, path), range(40)))
        seq_avg = statistics.mean(seq) * 1000
        conc_avg = statistics.mean(conc) * 1000
        conc_p95 = sorted(conc)[int(len(conc) * 0.95) - 1] * 1000
        metrics[path] = {
            'seq_avg_ms': round(seq_avg, 2),
            'conc_avg_ms': round(conc_avg, 2),
            'conc_p95_ms': round(conc_p95, 2),
        }
        if seq_avg > 20:
            raise AssertionError(f'{path} sequential average too high: {seq_avg:.2f}ms')
        if conc_avg > 80:
            raise AssertionError(f'{path} concurrent average too high: {conc_avg:.2f}ms')
        if conc_p95 > 160:
            raise AssertionError(f'{path} concurrent p95 too high: {conc_p95:.2f}ms')
    return metrics


def main() -> None:
    proc, base_url, data_dir = start_server(board_only=False)
    try:
        wait_ready(base_url)
        assert_security_headers(base_url)
        performance = assert_performance(base_url)
        assert_backup_restore_roundtrip(base_url)
        print(json.dumps({'ok': True, 'performance': performance}, ensure_ascii=False))
        print('OPERATIONAL_QUALITY_OK')
    finally:
        output = stop_server(proc, data_dir)
        if proc.returncode not in (0, -15):
            raise RuntimeError(f'quality server failed\n{output}')


if __name__ == '__main__':
    main()
