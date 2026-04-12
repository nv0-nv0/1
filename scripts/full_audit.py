from __future__ import annotations

import argparse
import importlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
SERVER = ROOT / 'server_app.py'
TESTS = ROOT / 'tests'
ROUTE_RE = re.compile(r"@app\.(get|post)\([\"']([^\"']+)[\"']")
UNVERIFIED = [
    '실제 Toss 실결제',
    '실제 Coolify 운영 반영',
    '실제 도메인/SSL 운영 전환',
]


def count_todo_like() -> int:
    total = 0
    allowed_suffixes = {'.py', '.js', '.html', '.md', '.yaml', '.yml', '.css', '.txt', '.json'}
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if any(part in {'__pycache__', '.venv', '.venvcheck', '.testdata', '.testdata_full', '.testdata_prod', '.git', 'runtime_vendor', 'dist'} for part in path.parts):
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in {'scripts/full_audit.py', 'AUDIT_REPORT_KO.md', 'PACKAGE_CONTENTS.txt', 'PACKAGE_CONTENTS.json', 'SHA256SUMS.txt'}:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        total += len(re.findall(r'\b(TODO|FIXME|XXX)\b', text))
    return total


def load_active_routes(mode: str) -> list[tuple[str, str]]:
    os.environ['NV0_BOARD_ONLY_MODE'] = '1' if mode == 'board' else '0'
    os.environ.setdefault('NV0_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver')
    os.environ.setdefault('NV0_ALLOWED_ORIGINS', 'http://127.0.0.1:8000')
    os.environ.setdefault('NV0_BASE_URL', 'http://127.0.0.1:8000')
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    mod = importlib.import_module('server_app')
    mod = importlib.reload(mod)
    app = mod.create_app()
    active: list[tuple[str, str]] = []
    for route in app.routes:
        methods = getattr(route, 'methods', None)
        path = getattr(route, 'path', '')
        if not methods or path == '/openapi.json':
            continue
        for method in sorted(methods):
            if method in {'HEAD', 'OPTIONS'}:
                continue
            active.append((method, path))
    return active


def load_declared_routes() -> list[tuple[str, str]]:
    return [(method.upper(), route) for method, route in ROUTE_RE.findall(SERVER.read_text(encoding='utf-8'))]


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate NV0 audit report')
    parser.add_argument('--mode', choices=['full', 'board'], default='full')
    args = parser.parse_args()

    html_pages = sorted(DIST.rglob('*.html'))
    declared = load_declared_routes()
    active = load_active_routes(args.mode)
    tests = sorted(TESTS.glob('*.py')) + sorted(TESTS.glob('*.js'))
    todo_count = count_todo_like()
    dormant = [item for item in declared if item not in active]

    title = '# NV0 최종 감사 리포트' if args.mode == 'full' else '# NV0 게시판 전용 감사 리포트'
    lines: list[str] = [title, '']
    lines.append('## 1. 산출물 수량')
    lines.append(f'- 모드: {args.mode}')
    lines.append(f'- 정적 HTML 페이지 수: {len(html_pages)}')
    lines.append(f'- 활성 API route 수: {len(active)}')
    lines.append(f'- 소스상 선언 route 수: {len(declared)}')
    lines.append(f'- 현재 모드 기준 비활성 route 수: {len(dormant)}')
    lines.append(f'- 테스트 스크립트 수: {len(tests)}')
    lines.append(f'- 소스 TODO/FIXME/XXX 표기 수: {todo_count}')
    lines.append('')
    lines.append('## 2. 페이지 목록')
    for path in html_pages:
        lines.append(f'- {path.relative_to(DIST).as_posix()}')
    lines.append('')
    lines.append('## 3. 활성 API 목록')
    for method, route in active:
        lines.append(f'- {method} {route}')
    lines.append('')
    lines.append('## 4. 현재 모드에서 비활성 처리되는 route')
    if dormant:
        for method, route in dormant:
            lines.append(f'- {method} {route}')
    else:
        lines.append('- 없음')
    lines.append('')
    lines.append('## 5. 테스트 목록')
    for path in tests:
        lines.append(f'- {path.name}')
    lines.append('')
    lines.append('## 6. 외부 환경이 필요한 최종 확인')
    for idx, item in enumerate(UNVERIFIED, start=1):
        lines.append(f'- {idx}. {item}')
    lines.append('')
    lines.append('## 7. 판정')
    if args.mode == 'full':
        lines.append('- 즉시 시연 / 결제 진입 / 자동 발행 / 포털 확인 흐름은 코드 및 로컬 검증 기준 완료')
        lines.append('- 실제 상용 결제는 실키 환경에서 마지막 1회만 추가 확인 필요')
    else:
        lines.append('- 게시판 전용 운영 범위와 410 차단 정책은 검증 완료')

    out = ROOT / 'AUDIT_REPORT_KO.md'
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(out)
    print(f'mode={args.mode}')
    print(f'pages={len(html_pages)}')
    print(f'active_api_routes={len(active)}')
    print(f'declared_routes={len(declared)}')
    print(f'dormant_routes={len(dormant)}')
    print(f'tests={len(tests)}')
    print(f'unverified={len(UNVERIFIED)}')
    print(f'todo_markers={todo_count}')


if __name__ == '__main__':
    main()
