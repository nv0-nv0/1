# NV0 최종 납품 검증 보고서

작성일: 2026-04-12

## 최종 판정
- 개발 가능: 예
- 배포 가능: 예
- 즉시 시연(Veridion 포함): 예
- 결제 후 자동 발행/납품 구조: 예
- board-only 회귀 운영: 예

## 원본 대비 정리 원칙
- 원본 ZIP의 파일 수 대부분은 `.venv` 및 `.venvcheck` 런타임 묶음이 차지했습니다.
- 최종 납품본은 원본 핵심 자산을 보존하면서, 테스트 잔재/캐시/중복 런타임을 제거한 정리본입니다.
- 원본 배포 보조 파일 `dist/robots.txt`, `dist/sitemap.xml`, `dist/.well-known/security.txt`는 복원했습니다.

## 최종 패키지 상태
- 실제 파일 수: 800개
- 실제 내용물 크기: 약 33.03MB
- 오프라인 런타임 포함: `runtime_vendor/`
- 개발/배포 핵심 포함: `src/`, `dist/`, `scripts/`, `tests/`, `server_app.py`, `Dockerfile`, `compose.coolify.yaml`, `.env.example`

## 포함된 핵심 배포 페이지
- `/products/veridion/`
- `/checkout/`
- `/payments/toss/success/`
- `/portal/`
- `/board/`
- `/admin/`
- `/legal/privacy/`
- `/robots.txt`
- `/sitemap.xml`
- `/.well-known/security.txt`

## 검증 완료 항목
- `python3 tests/test_all.py`
- `python3 tests/robustness_check.py`
- `python3 tests/packaging_runtime_check.py`
- `python3 tests/content_integrity_check.py`
- `python3 tests/config_integrity_check.py`
- `python3 scripts/full_audit.py --mode full`
- `python3 -m uvicorn server_app:app ...` + `python3 scripts/smoke_release.py --base-url http://127.0.0.1:8091 --mode full`
- `python3 -m uvicorn server_app:app ...` + `python3 scripts/smoke_release.py --base-url http://127.0.0.1:8092 --mode board`

## 납품본에서 의도적으로 제거한 항목
- `.venv/`
- `.venvcheck/`
- `.testdata*`
- `__pycache__/`, `*.pyc`
- SQLite 실행 중 생성되는 `*.db-shm`, `*.db-wal`
- 백업/캐시성 잔재

## 주의사항
- 실제 Toss 라이브 결제는 운영 환경에서 실키로 소액 1회 최종 검증이 필요합니다.
- 코드/패키지 기준으로는 최종 완성본입니다.
