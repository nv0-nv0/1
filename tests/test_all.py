from pathlib import Path
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import time
from urllib.request import urlopen
from html.parser import HTMLParser
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
PORT = 8032


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, format, *args):
        pass


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        amap = dict(attrs)
        for key in ('href', 'src'):
            if key in amap:
                self.links.append(amap[key])


def start_server():
    httpd = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def check_http(path: str):
    with urlopen(f'http://127.0.0.1:{PORT}{path}') as res:
        if res.status != 200:
            raise RuntimeError(f'{path} => {res.status}')


def run_step(label: str, cmd: list[str], *, timeout: int = 240):
    print(f'RUNNING:{label}', flush=True)
    subprocess.run(cmd, check=True, timeout=timeout)
    print(f'OK:{label}', flush=True)


def check_links():
    missing = []
    for html_path in DIST.rglob('*.html'):
        parser = AssetParser()
        parser.feed(html_path.read_text(encoding='utf-8'))
        for raw in parser.links:
            cleaned = urlsplit(raw)
            link = cleaned.path
            if not link or raw.startswith(('http://', 'https://', 'mailto:', 'tel:', '#', 'javascript:')):
                continue
            target = (html_path.parent / link).resolve()
            if target.is_dir():
                target = target / 'index.html'
            if not target.exists():
                missing.append((html_path.relative_to(DIST).as_posix(), raw))
    if missing:
        raise RuntimeError('Broken local links/assets: ' + '; '.join([f'{page} -> {link}' for page, link in missing[:20]]))




def cleanup_runtime_artifacts():
    removable_dirs = [
        ROOT / '.testdata',
        ROOT / '.testdata_full',
        ROOT / '.testdata_prod',
    ]
    for path in removable_dirs:
        shutil.rmtree(path, ignore_errors=True)
    for cache_dir in ROOT.rglob('__pycache__'):
        shutil.rmtree(cache_dir, ignore_errors=True)

def main():
    cleanup_runtime_artifacts()
    try:
        run_step('py_compile', ['python3', '-m', 'py_compile',
            str(ROOT / 'server_app.py'),
            str(ROOT / 'build.py'),
            str(ROOT / 'scripts' / 'backup_state.py'),
            str(ROOT / 'scripts' / 'restore_state.py'),
            str(ROOT / 'scripts' / 'preflight_env.py'),
            str(ROOT / 'tests' / 'api_deploy_check.py'),
            str(ROOT / 'tests' / 'full_api_e2e_check.py'),
            str(ROOT / 'tests' / 'content_integrity_check.py'),
            str(ROOT / 'tests' / 'config_integrity_check.py'),
            str(ROOT / 'tests' / 'packaging_runtime_check.py'),
            str(ROOT / 'tests' / 'board_only_scope_check.py'),
            str(ROOT / 'tests' / 'robustness_check.py'),
            str(ROOT / 'tests' / 'delivery_package_completeness_check.py'),
            str(ROOT / 'tests' / 'release_smoke_check.py'),
            str(ROOT / 'tests' / 'operational_quality_check.py'),
            str(ROOT / 'tests' / 'product_surface_e2e_check.py'),
            str(ROOT / 'tests' / 'post_deploy_verify_local_check.py'),
            str(ROOT / 'tests' / 'canonical_default_enforcement_check.py'),
            str(ROOT / 'tests' / 'healthcheck_surface_check.py'),
            str(ROOT / 'scripts' / 'post_deploy_verify.py'),
        ], timeout=120)
        run_step('preflight_env', ['bash', '-lc', f'set -a && . "{ROOT / ".env.example"}" && set +a && python3 "{ROOT / "scripts" / "preflight_env.py"}"'], timeout=120)
        run_step('build', ['python3', str(ROOT / 'build.py')], timeout=180)
        print('RUNNING:link_check', flush=True)
        check_links()
        print('OK:link_check', flush=True)
        httpd = start_server()
        time.sleep(0.4)
        try:
            print('RUNNING:http_check', flush=True)
            for path in ['/', '/products/', '/products/veridion/', '/checkout/', '/portal/', '/board/', '/admin/', '/legal/privacy/', '/legal/terms/', '/robots.txt', '/sitemap.xml', '/404.html']:
                check_http(path)
            print('OK:http_check', flush=True)
        finally:
            httpd.shutdown()
            httpd.server_close()
        run_step('runtime_engine_check', ['node', str(ROOT / 'tests' / 'runtime_engine_check.js')], timeout=120)
        run_step('full_api_e2e_check', ['python3', str(ROOT / 'tests' / 'full_api_e2e_check.py')], timeout=240)
        run_step('api_deploy_check', ['python3', str(ROOT / 'tests' / 'api_deploy_check.py')], timeout=240)
        run_step('content_integrity_check', ['python3', str(ROOT / 'tests' / 'content_integrity_check.py')], timeout=120)
        run_step('config_integrity_check', ['python3', str(ROOT / 'tests' / 'config_integrity_check.py')], timeout=120)
        run_step('board_only_scope_check', ['python3', str(ROOT / 'tests' / 'board_only_scope_check.py')], timeout=120)
        run_step('robustness_check', ['python3', str(ROOT / 'tests' / 'robustness_check.py')], timeout=240)
        run_step('release_smoke_check', ['python3', str(ROOT / 'tests' / 'release_smoke_check.py')], timeout=240)
        run_step('delivery_package_completeness_check', ['python3', str(ROOT / 'tests' / 'delivery_package_completeness_check.py')], timeout=240)
        run_step('operational_quality_check', ['python3', str(ROOT / 'tests' / 'operational_quality_check.py')], timeout=300)
        run_step('product_surface_e2e_check', ['python3', str(ROOT / 'tests' / 'product_surface_e2e_check.py')], timeout=300)
        run_step('packaging_runtime_check', ['python3', str(ROOT / 'tests' / 'packaging_runtime_check.py')], timeout=240)
        run_step('post_deploy_verify_local_check', ['python3', str(ROOT / 'tests' / 'post_deploy_verify_local_check.py')], timeout=300)
        run_step('canonical_default_enforcement_check', ['python3', str(ROOT / 'tests' / 'canonical_default_enforcement_check.py')], timeout=180)
        run_step('healthcheck_surface_check', ['python3', str(ROOT / 'tests' / 'healthcheck_surface_check.py')], timeout=180)
        print('ALL_TESTS_OK', flush=True)
    finally:
        cleanup_runtime_artifacts()


if __name__ == '__main__':
    main()
