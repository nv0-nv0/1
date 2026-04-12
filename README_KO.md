# NV0 최종 납품 패키지

NV0는 **즉시 시연형 제품 데모 + 외부 결제 연동 + 결제 직후 자동 발행/납품 + 자동발행 게시판 운영**을 한 패키지로 묶은 정적 사이트 + FastAPI 런타임 프로젝트입니다.

현재 패키지는 **전체판(full mode)을 기본값**으로 두고 있으며, 환경변수 한 줄로 **게시판 전용판(board-only mode)** 으로도 전환할 수 있습니다.

## 포함 범위
- 즉시 시연형 제품 데모
- 제품 소개 / 가격 / 문서 / 사례 / FAQ / 온보딩 페이지
- Veridion / ClearPort / GrantOps / DraftForge 제품 상세 페이지
- 외부 결제 진입 및 Toss 결제 승인/실패 처리
- 결제 완료 후 자동 발행 / 결과 팩 생성 / 고객 포털 조회
- 관리자 허브: 주문 / 데모 / 문의 / 발행 / 백업 / 복구 검증
- 자동발행 게시판 운영
- full mode / board-only mode 동시 지원

## 실행 모드
### 1) full mode (기본)
사용자 요구 흐름 전체를 켭니다.
- 제품 페이지 즉시 시연
- 결제 버튼 노출
- 외부 결제 진입
- 결제 승인 후 자동 발행
- 고객 포털 납품 확인
- 관리자 주문 조작 API

### 2) board-only mode
게시판 운영만 남기고 판매 축을 끕니다.
- 홈 / 게시판 / 관리자 / 개인정보처리방침만 노출
- 주문 / 결제 / 데모 / 문의 / 포털은 `410 Gone`

전환값:
```bash
NV0_BOARD_ONLY_MODE=0   # 전체판
NV0_BOARD_ONLY_MODE=1   # 게시판 전용판
```

## 공개 페이지
### full mode
- `/`
- `/products/`
- `/products/veridion/`
- `/products/clearport/`
- `/products/grantops/`
- `/products/draftforge/`
- `/checkout/`
- `/demo/`
- `/contact/`
- `/portal/`
- `/pricing/`
- `/company/`
- `/cases/`
- `/docs/`
- `/faq/`
- `/board/`
- `/admin/`
- `/legal/privacy/`
- `/legal/refund/`
- `/payments/toss/success/`
- `/payments/toss/fail/`

### board-only mode
- `/`
- `/board/`
- `/admin/`
- `/legal/privacy/`

## 주요 API
### public
- `GET /api/health`
- `GET /api/public/system-config`
- `GET /api/public/board/feed`
- `POST /api/public/demo-requests`
- `POST /api/public/contact-requests`
- `POST /api/public/orders`
- `POST /api/public/orders/reserve`
- `POST /api/public/payments/toss/confirm`
- `POST /api/public/payments/toss/webhook`
- `POST /api/public/portal/lookup`

### admin
- `GET /api/admin/health`
- `GET /api/admin/validate`
- `GET /api/admin/state`
- `GET /api/admin/export`
- `POST /api/admin/import`
- `POST /api/admin/actions/publish-now`
- `POST /api/admin/actions/reseed-board`
- `POST /api/admin/actions/reset`
- `POST /api/admin/actions/seed-demo`
- `POST /api/admin/orders/{order_id}/advance`
- `POST /api/admin/orders/{order_id}/republish`
- `POST /api/admin/orders/{order_id}/toggle-payment`

## 로컬 실행
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 build.py
uvicorn server_app:app --host 127.0.0.1 --port 8000
```

## 환경변수 핵심
`.env.example`를 기본값으로 사용하면 됩니다.

필수에 가까운 값:
- `NV0_BASE_URL`
- `NV0_ADMIN_TOKEN`
- `NV0_BACKUP_PASSPHRASE`
- `NV0_ALLOWED_HOSTS`
- `NV0_ALLOWED_ORIGINS`
- `NV0_BOARD_ONLY_MODE`

결제 관련:
- `NV0_PAYMENT_PROVIDER=toss`
- `NV0_TOSS_CLIENT_KEY`
- `NV0_TOSS_SECRET_KEY`
- `NV0_TOSS_WEBHOOK_SECRET`
- `NV0_TOSS_MOCK=1` 테스트 / `0` 실결제

운영 권장:
- 관리자 토큰 32자 이상
- 백업 암호 24자 이상
- `NV0_ENABLE_DOCS=0`
- `NV0_ENFORCE_CANONICAL_HOST=1`
- `NV0_HSTS_ENABLED=1`

## 테스트
전체 검증:
```bash
python3 tests/test_all.py
```

개별 검증:
```bash
python3 tests/full_api_e2e_check.py
python3 tests/board_only_scope_check.py
python3 tests/packaging_runtime_check.py
python3 tests/robustness_check.py
python3 scripts/full_audit.py
```

배포 후 스모크 테스트:
```bash
python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode full
python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode board
```

최종 납품 패키지 생성:
```bash
python3 scripts/create_delivery_package.py
```

## Docker / Coolify
- `Dockerfile` 포함
- `compose.coolify.yaml` 포함
- `/app/data`, `/app/backups` 영구 볼륨 사용
- 기본 컨테이너는 read-only rootfs 기준으로 설정

## 실제 상용 검증에서 꼭 남는 1단계
이 패키지는 **코드/페이지/API/자동발행/포털 흐름**까지 모두 검증됐습니다.
다만 **실제 Toss 상용 결제**는 실키를 넣은 운영/스테이징 환경에서 **소액 1회 실결제**를 마지막으로 확인해야 합니다.

이 항목은 코드 미완성 때문이 아니라, 외부 결제사 연동 특성상 실제 키와 실제 리다이렉트 URL이 있어야만 끝나는 단계입니다.

## 납품 문서
- `README_KO.md` : 전체 개요
- `INTEGRATION_MAP.md` : 페이지/API/흐름 맵
- `AUDIT_REPORT_KO.md` : 감사 요약
- `FINAL_REAL_COMPLETION_REPORT_KO.md` : 완료 판정
- `DELIVERY_RUNBOOK_KO.md` : 실배포/복구/검증 절차
