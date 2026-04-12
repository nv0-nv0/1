#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fetch_state(base: str, token: str) -> dict:
    req = Request(base.rstrip('/') + '/api/admin/export', method='GET')
    if token:
        req.add_header('X-Admin-Token', token)
    with urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8'))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hmac_sha256_bytes(value: bytes, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), value, hashlib.sha256).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_sha256(path: Path) -> Path:
    sha_path = Path(str(path) + '.sha256')
    sha_path.write_text(f"{sha256_file(path)}  {path.name}\n", encoding='utf-8')
    sha_path.chmod(0o600)
    return sha_path


def encrypt_file(src: Path, dest: Path, passphrase: str) -> None:
    env = os.environ.copy()
    env['NV0_BACKUP_PASSPHRASE'] = passphrase
    subprocess.run([
        'openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-iter', '200000',
        '-in', str(src), '-out', str(dest), '-pass', 'env:NV0_BACKUP_PASSPHRASE'
    ], check=True, env=env)


def prune_backups(directory: Path, keep: int, prefix: str) -> None:
    files = sorted([p for p in directory.iterdir() if p.is_file() and p.name.startswith(prefix) and not p.name.endswith('.sha256')])
    for stale in files[:-keep]:
        stale.unlink(missing_ok=True)
        Path(str(stale) + '.sha256').unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default=os.getenv('NV0_BACKUP_DIR', 'backups'))
    parser.add_argument('--base-url', default=os.getenv('NV0_BASE_URL', 'http://127.0.0.1:8000'))
    parser.add_argument('--retention', type=int, default=int(os.getenv('NV0_BACKUP_RETENTION', '28') or '28'))
    parser.add_argument('--prefix', default=os.getenv('NV0_BACKUP_PREFIX', 'nv0-backup'))
    parser.add_argument('--passphrase-env', default='NV0_BACKUP_PASSPHRASE')
    parser.add_argument('--allow-plaintext', action='store_true')
    args = parser.parse_args()

    base = str(args.base_url).rstrip('/')
    token = os.getenv('NV0_ADMIN_TOKEN', '')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    payload = fetch_state(base, token)
    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    state = payload.get('state', {}) if isinstance(payload, dict) else {}
    manifest = {
        'createdAt': stamp,
        'baseUrl': base,
        'format': 'nv0-state-export-v2',
        'payloadSha256': sha256_bytes(payload_bytes),
        'recordCounts': {key: len(value or []) for key, value in state.items() if isinstance(value, list)},
    }

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        payload_file = tmp / 'export.json'
        manifest_file = tmp / 'manifest.json'
        archive_file = tmp / f'{args.prefix}-{stamp}.tar.gz'
        payload_file.write_bytes(payload_bytes)
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        with tarfile.open(archive_file, 'w:gz') as tar:
            tar.add(payload_file, arcname='export.json')
            tar.add(manifest_file, arcname='manifest.json')

        passphrase = os.getenv(args.passphrase_env, '')
        if not passphrase and not args.allow_plaintext:
            raise SystemExit('backup encryption passphrase is required unless --allow-plaintext is used explicitly')
        if passphrase:
            signable = payload_bytes + b'\n' + json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode('utf-8')
            manifest['manifestHmacSha256'] = hmac_sha256_bytes(signable, passphrase)
            manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            with tarfile.open(archive_file, 'w:gz') as tar:
                tar.add(payload_file, arcname='export.json')
                tar.add(manifest_file, arcname='manifest.json')
            final_path = output_dir / f'{args.prefix}-{stamp}.tar.gz.enc'
            encrypt_file(archive_file, final_path, passphrase)
        else:
            final_path = output_dir / f'{args.prefix}-{stamp}.tar.gz'
            shutil.copy2(archive_file, final_path)

    final_path.chmod(0o600)
    write_sha256(final_path)
    prune_backups(output_dir, max(1, args.retention), args.prefix)
    print(final_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
