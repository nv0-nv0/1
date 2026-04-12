from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'create_delivery_package.py'

REQUIRED_PATHS = {
    '.github/workflows/ci.yml',
    '.testdata/nv0.db',
    '.testdata_full/nv0.db',
    'FULL_PACKAGE_MANIFEST.json',
    'DELIVERY_PACKAGE_MANIFEST.json',
    'runtime_vendor/fastapi/__init__.py',
    'run_with_vendor.sh',
    'test_with_vendor.sh',
    'build.py',
    'server_app.py',
    'compose.coolify.yaml',
    'dist/index.html',
    'dist/products/veridion/index.html',
    'dist/legal/terms/index.html',
    'scripts/create_delivery_package.py',
    'tests/test_all.py',
    'tests/delivery_package_completeness_check.py',
}
DB_PATHS = ('.testdata/nv0.db', '.testdata_full/nv0.db')
SIDE_CARS = ('.testdata/nv0.db-wal', '.testdata/nv0.db-shm', '.testdata_full/nv0.db-wal', '.testdata_full/nv0.db-shm')


def source_file_count() -> int:
    candidates = []
    for item in ROOT.rglob('*'):
        if not item.is_file():
            continue
        if item.suffix in {'.zip', '.tar', '.log', '.pyc', '.pyo', '.pyd'}:
            continue
        if item.name.endswith(('-wal', '-shm')):
            continue
        if any(part in {'__pycache__', '.venv', '.venvcheck', '.git', '.pytest_cache', 'node_modules'} for part in item.parts):
            continue
        if item.name in {'PACKAGE_CONTENTS.txt', 'PACKAGE_CONTENTS.json', 'SHA256SUMS.txt', 'DELIVERY_PACKAGE_MANIFEST.json'}:
            continue
        candidates.append(item)
    return len(candidates)


def verify_sqlite(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        cur = con.cursor()
        cur.execute('PRAGMA integrity_check')
        row = cur.fetchone()
        if not row or row[0] != 'ok':
            raise AssertionError(f'integrity check failed for {path}: {row}')
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        if cur.fetchone()[0] < 1:
            raise AssertionError(f'no tables found in {path}')
        cur.execute('SELECT COUNT(*) FROM records')
        if cur.fetchone()[0] < 1:
            raise AssertionError(f'no records found in {path}')
    finally:
        con.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='nv0-delivery-pkg-') as tmp:
        outdir = Path(tmp)
        package_name = 'nv0_delivery_verification_full'
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--output-dir', str(outdir), '--name', package_name, '--mode', 'full'],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
        payload = json.loads(result.stdout.strip())
        package_dir = Path(payload['package_dir'])
        zip_path = Path(payload['zip'])
        tar_path = Path(payload['tar'])
        if not package_dir.exists() or not zip_path.exists() or not tar_path.exists():
            raise AssertionError('package outputs missing')

        archived_files = {p.relative_to(package_dir).as_posix() for p in package_dir.rglob('*') if p.is_file()}
        missing = sorted(path for path in REQUIRED_PATHS if path not in archived_files)
        if missing:
            raise AssertionError(f'required package paths missing: {missing}')
        expected_min = int(source_file_count() * 0.97)
        if payload['package_file_count'] < expected_min:
            raise AssertionError(f"package file count too low: {payload['package_file_count']} < {expected_min}")
        if zip_path.stat().st_size < 5_000_000 or tar_path.stat().st_size < 30_000_000:
            raise AssertionError('archive unexpectedly too small')
        if not payload.get('db_prepare'):
            raise AssertionError('database preparation results missing')
        for item in payload['db_prepare']:
            if item['integrity_check'] != 'ok':
                raise AssertionError(f'database integrity failed: {item}')

        with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory(prefix='nv0-zip-check-') as ztmp:
            z_names = set(zf.namelist())
            for required in REQUIRED_PATHS:
                if required not in z_names:
                    raise AssertionError(f'zip missing required path: {required}')
            for side in SIDE_CARS:
                if side in z_names:
                    raise AssertionError(f'zip should not include runtime sqlite sidecar: {side}')
            for db_rel in DB_PATHS:
                zf.extract(db_rel, ztmp)
                verify_sqlite(Path(ztmp) / db_rel)

        with tarfile.open(tar_path) as tf, tempfile.TemporaryDirectory(prefix='nv0-tar-check-') as ttmp:
            t_names = {m.name for m in tf.getmembers() if m.isfile()}
            for required in REQUIRED_PATHS:
                if required not in t_names:
                    raise AssertionError(f'tar missing required path: {required}')
            for side in SIDE_CARS:
                if side in t_names:
                    raise AssertionError(f'tar should not include runtime sqlite sidecar: {side}')
            for db_rel in DB_PATHS:
                tf.extract(db_rel, ttmp)
                verify_sqlite(Path(ttmp) / db_rel)
            if len(tf.getmembers()) > payload['package_file_count'] * 2:
                raise AssertionError('tar archive contains unexpected duplicate entries')

    print('DELIVERY_PACKAGE_COMPLETENESS_OK')


if __name__ == '__main__':
    main()
