from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TOP_LEVEL_DIRS = {'assets', 'admin', 'board', 'legal', '.well-known'}
ALLOWED_ROOT_FILES = {'index.html', 'robots.txt', 'sitemap.xml'}
ALLOWED_HTML = {
    'index.html',
    'board/index.html',
    'admin/index.html',
    'legal/privacy/index.html',
}
EXPECTED_API_ROUTES = {
    ('GET', '/api/health'),
    ('GET', '/api/admin/health'),
    ('GET', '/api/public/system-config'),
    ('GET', '/api/admin/validate'),
    ('GET', '/api/admin/state'),
    ('GET', '/api/admin/export'),
    ('POST', '/api/admin/import'),
    ('GET', '/api/public/board/feed'),
    ('POST', '/api/admin/actions/publish-now'),
    ('POST', '/api/admin/actions/reseed-board'),
    ('POST', '/api/admin/actions/reset'),
}
FORBIDDEN_ROUTE_PREFIXES = (
    '/api/public/orders',
    '/api/public/payments',
    '/api/public/demo-requests',
    '/api/public/contact-requests',
    '/api/public/portal/lookup',
    '/api/admin/orders/',
    '/api/admin/actions/seed-demo',
)


def assert_dist_scope(dist: Path) -> None:
    top_dirs = {p.name for p in dist.iterdir() if p.is_dir()}
    top_files = {p.name for p in dist.iterdir() if p.is_file()}
    extra_dirs = sorted(top_dirs - ALLOWED_TOP_LEVEL_DIRS)
    extra_files = sorted(top_files - ALLOWED_ROOT_FILES)
    if extra_dirs:
        raise AssertionError(f'extra dist dirs remain: {extra_dirs}')
    if extra_files:
        raise AssertionError(f'extra dist files remain: {extra_files}')
    html_pages = {p.relative_to(dist).as_posix() for p in dist.rglob('*.html')}
    missing = sorted(ALLOWED_HTML - html_pages)
    extra = sorted(html_pages - ALLOWED_HTML)
    if missing or extra:
        raise AssertionError(f'html scope mismatch missing={missing} extra={extra}')
    if not (dist / '.well-known' / 'security.txt').exists():
        raise AssertionError('missing .well-known/security.txt')


def import_server_app():
    os.environ['NV0_BOARD_ONLY_MODE'] = '1'
    os.environ.setdefault('NV0_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver')
    os.environ.setdefault('NV0_ALLOWED_ORIGINS', 'http://127.0.0.1:8000')
    os.environ.setdefault('NV0_BASE_URL', 'http://127.0.0.1:8000')
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    mod = importlib.import_module('server_app')
    mod = importlib.reload(mod)
    return mod


def assert_api_scope() -> None:
    mod = import_server_app()
    app = mod.create_app()
    routes = set()
    for route in app.routes:
        methods = getattr(route, 'methods', None)
        path = getattr(route, 'path', '')
        if not methods or path == '/openapi.json':
            continue
        if path == '/':
            continue
        for method in methods:
            if method in {'HEAD', 'OPTIONS'}:
                continue
            routes.add((method, path))
    missing = sorted(EXPECTED_API_ROUTES - routes)
    if missing:
        raise AssertionError(f'missing api routes: {missing}')
    forbidden = sorted(item for item in routes if any(item[1] == prefix or item[1].startswith(prefix) for prefix in FORBIDDEN_ROUTE_PREFIXES))
    if forbidden:
        raise AssertionError(f'forbidden api routes still registered: {forbidden}')


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='nv0-board-only-') as tmp:
        repo = Path(tmp) / 'repo'
        shutil.copytree(ROOT, repo, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '.venvcheck', '.testdata*', '*.pyc'))
        shutil.rmtree(repo / 'dist', ignore_errors=True)
        env = os.environ.copy()
        env['NV0_BOARD_ONLY_MODE'] = '1'
        subprocess.run([sys.executable, str(repo / 'build.py')], cwd=str(repo), env=env, check=True, timeout=180)
        assert_dist_scope(repo / 'dist')
    assert_api_scope()
    print('BOARD_ONLY_SCOPE_OK')


if __name__ == '__main__':
    main()
