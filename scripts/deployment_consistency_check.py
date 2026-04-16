from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / 'compose.coolify.yaml'
ENV_EXAMPLE = ROOT / '.env.example'
ENV_PROD = ROOT / '.env.production.example'
RUNBOOK = ROOT / 'DELIVERY_RUNBOOK_KO.md'
README = ROOT / 'README_KO.md'
DOCKERFILE = ROOT / 'Dockerfile'

ENV_REF_RE = re.compile(r'\$\{([A-Z0-9_]+)(?::[^}]*)?\}')
ASSIGN_RE = re.compile(r'^([A-Z0-9_]+)=', re.M)
SCRIPT_RE = re.compile(r'scripts/[\w.-]+\.py')
FILE_REFS = [
    'compose.coolify.yaml', 'Dockerfile', '.env.example', '.env.production.example',
    'DELIVERY_RUNBOOK_KO.md', 'README_KO.md', 'COOLIFY_APP_DEPLOYMENT_KO.md', 'scripts/package_completion_gate.py',
    'scripts/post_deploy_verify.py', 'scripts/preflight_env.py', 'scripts/product_runtime_e2e.py',
    'scripts/result_quality_gate.py', 'scripts/api_safety_regression.py', 'scripts/board_mode_regression.py',
    'scripts/deployment_consistency_check.py',
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def env_keys(path: Path) -> set[str]:
    return set(ASSIGN_RE.findall(path.read_text(encoding='utf-8')))


def main() -> None:
    argparse.ArgumentParser(description='Check deploy-facing file consistency for NV0 package').parse_args()
    compose_text = COMPOSE.read_text(encoding='utf-8')
    env_refs = set(ENV_REF_RE.findall(compose_text))
    example_keys = env_keys(ENV_EXAMPLE)
    prod_keys = env_keys(ENV_PROD)

    missing_example = sorted(key for key in env_refs if key not in example_keys)
    missing_prod = sorted(key for key in env_refs if key not in prod_keys)
    require(not missing_example, f'.env.example missing compose variables: {missing_example}')
    require(not missing_prod, f'.env.production.example missing compose variables: {missing_prod}')

    require('read_only: true' in compose_text, 'compose.coolify.yaml should enforce read_only root filesystem')
    require('/readyz' in compose_text and '/readyz' in DOCKERFILE.read_text(encoding='utf-8'), 'Docker/compose healthcheck should target /readyz')
    require('NV0_STRICT_STARTUP' in compose_text, 'compose.coolify.yaml should include NV0_STRICT_STARTUP')
    require('NV0_TOSS_WEBHOOK_SECRET' in compose_text, 'compose.coolify.yaml should include NV0_TOSS_WEBHOOK_SECRET')
    require('FORWARDED_ALLOW_IPS' in compose_text, 'compose.coolify.yaml should include FORWARDED_ALLOW_IPS for proxy headers')
    require('UVICORN_PROXY_HEADERS' in compose_text, 'compose.coolify.yaml should include UVICORN_PROXY_HEADERS')

    runbook_text = RUNBOOK.read_text(encoding='utf-8')
    readme_text = README.read_text(encoding='utf-8')
    referenced_scripts = set(SCRIPT_RE.findall(runbook_text + '\n' + readme_text))
    require('tests/' not in runbook_text, 'runbook should not reference missing tests/ paths in deploy package')
    for rel in referenced_scripts:
        require((ROOT / rel).exists(), f'referenced script missing: {rel}')
    for rel in FILE_REFS:
        require((ROOT / rel).exists(), f'required deploy artifact missing: {rel}')

    print('DEPLOYMENT_CONSISTENCY_OK')
    print(f'compose_env_refs={len(env_refs)}')
    print(f'readme_runbook_scripts={len(referenced_scripts)}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'DEPLOYMENT_CONSISTENCY_FAIL: {exc}', file=sys.stderr)
        raise
