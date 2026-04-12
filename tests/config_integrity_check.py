from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assert_contains(text: str, needles: list[str], label: str):
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{label} missing: {missing}")


def main():
    dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
    compose = (ROOT / 'compose.coolify.yaml').read_text(encoding='utf-8')
    env_example = (ROOT / '.env.example').read_text(encoding='utf-8')

    assert_contains(dockerfile, [
        'USER appuser',
        'EXPOSE 8000',
        'uvicorn server_app:app',
    ], 'dockerfile')

    assert_contains(compose, [
        'NV0_ALLOWED_ORIGINS:',
        'CMD-SHELL',
        "os.getenv('PORT','8000')",
        '/readyz',
        'nv0_company_data:/app/data',
        'nv0_company_backups:/app/backups',
        'nv0-company-backup',
        'no-new-privileges:true',
        'read_only: true',
        'tmpfs:',
        'user: "10001:10001"',
        '${NV0_ADMIN_TOKEN:?',
        '${NV0_BACKUP_PASSPHRASE:?',
    ], 'compose')

    assert_contains(env_example, [
        'NV0_ALLOWED_ORIGINS=',
        'NV0_ALLOWED_HOSTS=',
        'NV0_INTERNAL_HOSTS=',
        'NV0_TOSS_CLIENT_KEY=',
        'NV0_TOSS_SECRET_KEY=',
        'NV0_TOSS_WEBHOOK_SECRET=',
        'NV0_BACKUP_PASSPHRASE=',
        'NV0_BACKUP_RETENTION=',
        'NV0_REQUIRE_ADMIN_TOKEN=',
        'NV0_MAX_BODY_BYTES=',
        'NV0_ENFORCE_CANONICAL_HOST=',
        'NV0_CANONICAL_HOST=',
    ], 'env-example')

    print('CONFIG_OK')


if __name__ == '__main__':
    main()
