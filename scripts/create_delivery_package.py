from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import sqlite3
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now(timezone.utc).strftime('%Y%m%d')
DEFAULT_NAME = f'nv0_delivery_package_{STAMP}'

BASE_EXCLUDE_DIR_NAMES = {
    '__pycache__', '.venv', '.venvcheck', '.git', '.pytest_cache', 'node_modules',
}
BASE_EXCLUDE_FILE_SUFFIXES = {'.pyc', '.pyo', '.pyd', '.log'}
BASE_EXCLUDE_PATTERNS = {'*.zip', '*.tar', '*.tar.gz'}
BASE_EXCLUDE_RELATIVE = {'.DS_Store'}
CLEAN_MODE_EXTRA_EXCLUDE_DIR_NAMES = {
    '.github', '.testdata', '.testdata_full', '.testdata_prod', 'runtime_vendor', 'reports',
}
CLEAN_MODE_EXTRA_EXACT = {
    'server_app.py.bak',
    'FULL_PACKAGE_MANIFEST.json',
    'NV0_TEST_PERF_REPORT_20260412.md',
    'FULL_RECOVERY_REPORT_20260412.md',
    'FINAL_HARDENING_REPORT_20260412.md',
    'run_with_vendor.sh',
    'test_with_vendor.sh',
    'NO_SHELL_NOTE_KO.md',
}
ROOT_MANIFEST_NAME = 'FULL_PACKAGE_MANIFEST.json'
PACKAGE_MANIFEST_NAME = 'DELIVERY_PACKAGE_MANIFEST.json'
PACKAGE_META_FILES = {ROOT_MANIFEST_NAME, PACKAGE_MANIFEST_NAME, 'PACKAGE_CONTENTS.txt', 'PACKAGE_CONTENTS.json', 'SHA256SUMS.txt'}
DB_GLOBS = ('.testdata/*.db', '.testdata_full/*.db', '.testdata_prod/*.db', 'data/*.db')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _matches_pattern(name: str, patterns: set[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def checkpoint_sqlite_db(path: Path) -> dict:
    info = {'path': path.as_posix(), 'checkpointed': False, 'vacuumed': False, 'integrity_check': 'not-run'}
    if not path.exists():
        return info
    con = sqlite3.connect(path)
    try:
        cur = con.cursor()
        cur.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        cur.fetchall()
        info['checkpointed'] = True
        cur.execute('PRAGMA integrity_check')
        row = cur.fetchone()
        info['integrity_check'] = row[0] if row else 'unknown'
        if info['integrity_check'] != 'ok':
            raise RuntimeError(f'sqlite integrity check failed for {path}: {info["integrity_check"]}')
        con.commit()
        cur.execute('VACUUM')
        info['vacuumed'] = True
        con.commit()
    finally:
        con.close()
    for suffix in ('-wal', '-shm'):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    return info


def prepare_runtime_state() -> list[dict]:
    results: list[dict] = []
    seen: set[Path] = set()
    for pattern in DB_GLOBS:
        for db in sorted(ROOT.glob(pattern)):
            if db in seen:
                continue
            seen.add(db)
            results.append(checkpoint_sqlite_db(db))
    return results


def should_skip(path: Path, *, mode: str, stage_root: Path | None = None) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    parts = set(path.parts)
    if stage_root and stage_root in path.parents:
        return True
    if path.name in BASE_EXCLUDE_DIR_NAMES:
        return True
    if parts & BASE_EXCLUDE_DIR_NAMES:
        return True
    if rel in BASE_EXCLUDE_RELATIVE:
        return True
    if path.suffix in BASE_EXCLUDE_FILE_SUFFIXES:
        return True
    if _matches_pattern(path.name, BASE_EXCLUDE_PATTERNS):
        return True
    if path.name.endswith(('-wal', '-shm')):
        return True
    if path.name in PACKAGE_META_FILES:
        return True
    if mode == 'clean':
        if path.name in CLEAN_MODE_EXTRA_EXCLUDE_DIR_NAMES or parts & CLEAN_MODE_EXTRA_EXCLUDE_DIR_NAMES:
            return True
        if path.name in CLEAN_MODE_EXTRA_EXACT or rel in CLEAN_MODE_EXTRA_EXACT:
            return True
        if path.suffix in {'.enc', '.sha256'}:
            return True
    return False


def iter_source_files(*, mode: str, stage_root: Path | None = None) -> Iterable[Path]:
    for item in sorted(ROOT.rglob('*')):
        if not item.is_file():
            continue
        if should_skip(item, mode=mode, stage_root=stage_root):
            continue
        yield item


def build_manifest_from_files(files: Iterable[Path], *, root: Path, package_name: str) -> dict:
    file_records = []
    total = 0
    for item in files:
        rel = item.relative_to(root).as_posix()
        size = item.stat().st_size
        total += size
        file_records.append({'path': rel, 'size': size, 'sha256': sha256_file(item)})
    return {
        'package_name': package_name,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'file_count': len(file_records),
        'total_bytes': total,
        'files': file_records,
    }


def write_inventory(package_dir: Path, manifest: dict) -> None:
    text_lines = [
        f"PACKAGE: {manifest['package_name']}",
        f"GENERATED_AT_UTC: {manifest['generated_at_utc']}",
        f"FILE_COUNT: {manifest['file_count']}",
        f"TOTAL_BYTES: {manifest['total_bytes']}",
        '',
    ]
    sums_lines = []
    for item in manifest['files']:
        text_lines.append(f"{item['path']} | {item['size']} | {item['sha256']}")
        sums_lines.append(f"{item['sha256']}  {item['path']}")
    (package_dir / 'PACKAGE_CONTENTS.txt').write_text('\n'.join(text_lines) + '\n', encoding='utf-8')
    (package_dir / 'PACKAGE_CONTENTS.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (package_dir / 'SHA256SUMS.txt').write_text('\n'.join(sums_lines) + '\n', encoding='utf-8')


def refresh_root_manifest(*, mode: str, stage_root: Path | None = None) -> dict:
    manifest = build_manifest_from_files(iter_source_files(mode=mode, stage_root=stage_root), root=ROOT, package_name='nv0-root-project')
    (ROOT / ROOT_MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def stage_package(package_dir: Path, *, mode: str) -> dict:
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    for src in iter_source_files(mode=mode, stage_root=package_dir):
        rel = src.relative_to(ROOT)
        dest = package_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    root_manifest = ROOT / ROOT_MANIFEST_NAME
    if mode == 'full' and root_manifest.exists():
        shutil.copy2(root_manifest, package_dir / ROOT_MANIFEST_NAME)
    manifest = build_manifest_from_files((p for p in sorted(package_dir.rglob('*')) if p.is_file()), root=package_dir, package_name=package_dir.name)
    (package_dir / PACKAGE_MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    write_inventory(package_dir, manifest)
    return manifest


def archive_package(package_dir: Path) -> tuple[Path, Path]:
    zip_path = package_dir.with_suffix('.zip')
    tar_path = package_dir.with_suffix('.tar')
    if zip_path.exists():
        zip_path.unlink()
    if tar_path.exists():
        tar_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for item in sorted(p for p in package_dir.rglob('*') if p.is_file()):
            zf.write(item, arcname=item.relative_to(package_dir).as_posix())
    with tarfile.open(tar_path, 'w') as tf:
        for item in sorted(package_dir.rglob('*')):
            tf.add(item, arcname=item.relative_to(package_dir).as_posix(), recursive=False)
    return zip_path, tar_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Create NV0 delivery package.')
    parser.add_argument('--output-dir', default=str(ROOT.parent), help='Directory where the package directory and archives will be created.')
    parser.add_argument('--name', default=DEFAULT_NAME, help='Package directory base name.')
    parser.add_argument('--mode', choices=['full', 'clean'], default='full', help='full keeps the whole shippable project; clean excludes runtime/vendor/test fixtures.')
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = output_dir / args.name

    db_prepare = prepare_runtime_state()
    root_manifest = refresh_root_manifest(mode=args.mode, stage_root=package_dir)
    manifest = stage_package(package_dir, mode=args.mode)
    zip_path, tar_path = archive_package(package_dir)

    print(json.dumps({
        'mode': args.mode,
        'package_dir': str(package_dir),
        'zip': str(zip_path),
        'tar': str(tar_path),
        'root_file_count': root_manifest['file_count'],
        'root_total_bytes': root_manifest['total_bytes'],
        'package_file_count': manifest['file_count'],
        'package_total_bytes': manifest['total_bytes'],
        'db_prepare': db_prepare,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
