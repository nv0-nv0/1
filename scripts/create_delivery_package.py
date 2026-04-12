from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now(timezone.utc).strftime('%Y%m%d')
DEFAULT_NAME = f'nv0_delivery_package_{STAMP}'
INCLUDE_FILES = [
    '.dockerignore',
    '.env.example',
    'Dockerfile',
    'Makefile',
    'README_KO.md',
    'INTEGRATION_MAP.md',
    'AUDIT_REPORT_KO.md',
    'FINAL_REAL_COMPLETION_REPORT_KO.md',
    'DELIVERY_RUNBOOK_KO.md',
    'PREEMPTIVE_HARDENING_REPORT_20260412.md',
    'CHANGELOG_DELIVERY_20260412.md',
    'build.py',
    'requirements.txt',
    'compose.coolify.yaml',
    'server_app.py',
]
INCLUDE_DIRS = ['src', 'scripts', 'tests', 'dist', 'data']
EXCLUDE_NAMES = {
    '__pycache__', '.venv', '.venvcheck', '.git', '.pytest_cache', 'node_modules',
    '.testdata', '.testdata_full', '.testdata_prod', '.github',
}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.pyd', '.zip', '.tar', '.enc', '.sha256', '.log'}
EXCLUDE_EXACT = {
    'server_app.py.bak',
    'FULL_PACKAGE_MANIFEST.json',
    'NV0_TEST_PERF_REPORT_20260412.md',
    'FULL_RECOVERY_REPORT_20260412.md',
    'FINAL_HARDENING_REPORT_20260412.md',
}


def should_skip(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return True
    if path.name in EXCLUDE_EXACT:
        return True
    if any(part in EXCLUDE_NAMES for part in path.parts):
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    if path.name.endswith(('-wal', '-shm')):
        return True
    return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def copy_entry(src: Path, dest_root: Path) -> None:
    rel = src.relative_to(ROOT)
    dest = dest_root / rel
    if src.is_dir():
        for item in src.rglob('*'):
            if item.is_dir() or should_skip(item):
                continue
            target = dest_root / item.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
    else:
        if should_skip(src):
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def build_manifest(package_dir: Path) -> dict:
    files = []
    total = 0
    for item in sorted(p for p in package_dir.rglob('*') if p.is_file()):
        rel = item.relative_to(package_dir).as_posix()
        size = item.stat().st_size
        total += size
        files.append({'path': rel, 'size': size, 'sha256': sha256_file(item)})
    return {
        'package_name': package_dir.name,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'file_count': len(files),
        'total_bytes': total,
        'files': files,
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


def archive_package(package_dir: Path) -> tuple[Path, Path]:
    zip_path = package_dir.with_suffix('.zip')
    tar_path = package_dir.with_suffix('.tar')
    if zip_path.exists():
        zip_path.unlink()
    if tar_path.exists():
        tar_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for item in sorted(p for p in package_dir.rglob('*') if p.is_file()):
            zf.write(item, arcname=f'{package_dir.name}/{item.relative_to(package_dir).as_posix()}')
    with tarfile.open(tar_path, 'w') as tf:
        tf.add(package_dir, arcname=package_dir.name)
    return zip_path, tar_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Create cleaned NV0 delivery package.')
    parser.add_argument('--output-dir', default=str(ROOT.parent), help='Directory where the package directory and archives will be created.')
    parser.add_argument('--name', default=DEFAULT_NAME, help='Package directory base name.')
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = output_dir / args.name
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    for rel in INCLUDE_FILES:
        copy_entry(ROOT / rel, package_dir)
    for rel in INCLUDE_DIRS:
        copy_entry(ROOT / rel, package_dir)

    manifest = build_manifest(package_dir)
    write_inventory(package_dir, manifest)
    zip_path, tar_path = archive_package(package_dir)

    print(json.dumps({
        'package_dir': str(package_dir),
        'zip': str(zip_path),
        'tar': str(tar_path),
        'file_count': manifest['file_count'],
        'total_bytes': manifest['total_bytes'],
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
