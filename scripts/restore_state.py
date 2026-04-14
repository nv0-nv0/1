#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


EXPECTED_MEMBERS = {'export.json', 'manifest.json'}


def hmac_sha256_bytes(value: bytes, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), value, hashlib.sha256).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_sidecar_checksum(src: Path) -> None:
    sidecar = Path(str(src) + '.sha256')
    if not sidecar.exists():
        return
    line = sidecar.read_text(encoding='utf-8').strip()
    expected = line.split()[0].strip().lower() if line else ''
    actual = sha256_file(src)
    if not expected or actual != expected:
        raise SystemExit(f'checksum mismatch: {src.name}')


def decrypt_if_needed(src: Path, tmpdir: Path, passphrase: str) -> Path:
    if not src.name.endswith('.enc'):
        return src
    out = tmpdir / src.name[:-4]
    env = os.environ.copy()
    env['NV0_BACKUP_PASSPHRASE'] = passphrase
    subprocess.run([
        'openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '200000',
        '-in', str(src), '-out', str(out), '-pass', 'env:NV0_BACKUP_PASSPHRASE'
    ], check=True, env=env)
    return out


def parse_backup(src: Path, passphrase: str) -> dict:
    verify_sidecar_checksum(src)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        working = decrypt_if_needed(src, tmp, passphrase)
        if working.suffix == '.json':
            payload = json.loads(working.read_text(encoding='utf-8'))
            return {'payload': payload, 'manifest': {'format': 'nv0-state-export-v1'}}
        extract_dir = tmp / 'extract'
        extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(working, 'r:gz') as tar:
            members = tar.getnames()
            if set(members) != EXPECTED_MEMBERS:
                raise SystemExit(f'backup members invalid: {members}')
            try:
                tar.extractall(extract_dir, filter='data')
            except TypeError:
                tar.extractall(extract_dir)
        export_file = extract_dir / 'export.json'
        manifest_file = extract_dir / 'manifest.json'
        payload = json.loads(export_file.read_text(encoding='utf-8'))
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        fmt = str(manifest.get('format') or '')
        if fmt not in {'nv0-state-export-v1', 'nv0-state-export-v2'}:
            raise SystemExit(f'unsupported backup format: {fmt}')
        expected_payload_sha = str(manifest.get('payloadSha256') or '').lower()
        actual_payload_sha = hashlib.sha256(export_file.read_bytes()).hexdigest()
        if expected_payload_sha and expected_payload_sha != actual_payload_sha:
            raise SystemExit('payload checksum mismatch')
        expected_manifest_hmac = str(manifest.get('manifestHmacSha256') or '').lower()
        if expected_manifest_hmac:
            if not passphrase:
                raise SystemExit('backup passphrase required to verify manifest HMAC')
            unsigned_manifest = dict(manifest)
            unsigned_manifest.pop('manifestHmacSha256', None)
            signable = export_file.read_bytes() + b'\n' + json.dumps(unsigned_manifest, ensure_ascii=False, sort_keys=True).encode('utf-8')
            actual_manifest_hmac = hmac_sha256_bytes(signable, passphrase)
            if actual_manifest_hmac != expected_manifest_hmac:
                raise SystemExit('manifest HMAC mismatch')
        return {'payload': payload, 'manifest': manifest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('backup')
    parser.add_argument('--base-url', default=os.getenv('NV0_BASE_URL', 'http://127.0.0.1:8000'))
    parser.add_argument('--replace', action='store_true', default=True)
    parser.add_argument('--admin-token', default=os.getenv('NV0_ADMIN_TOKEN', ''))
    parser.add_argument('--passphrase', default=os.getenv('NV0_BACKUP_PASSPHRASE', ''))
    parser.add_argument('--passphrase-env', default='NV0_BACKUP_PASSPHRASE')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()

    backup_path = Path(args.backup)
    if not backup_path.exists():
        raise SystemExit(f'backup not found: {backup_path}')

    passphrase = args.passphrase or os.getenv(args.passphrase_env, '')
    parsed = parse_backup(backup_path, passphrase)
    if args.verify_only:
        print(json.dumps({'ok': True, 'verified': True, 'manifest': parsed['manifest']}, ensure_ascii=False))
        return 0

    payload = parsed['payload']
    body = json.dumps({'replace': args.replace, 'state': payload.get('state', payload)}).encode('utf-8')
    req = Request(str(args.base_url).rstrip('/') + '/api/admin/import', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    token = args.admin_token or os.getenv('NV0_ADMIN_TOKEN', '')
    if token:
        req.add_header('X-Admin-Token', token)
    with urlopen(req, timeout=30) as res:
        print(res.read().decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
