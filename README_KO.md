# NV0 최종 납품 패키지

NV0는 **즉시 시연형 제품 데모 + 외부 결제 연동 + 결제 직후 자동 발행/납품 + 자료실 허브 운영**을 한 패키지로 묶은 정적 사이트 + FastAPI 런타임 프로젝트입니다.

현재 패키지는 **전체판(full mode)을 기본값**으로 두고 있으며, 환경변수 한 줄로 **자료실 전용판(board-only mode)** 으로도 전환할 수 있습니다.

## 포함 범위
- 즉시 시연형 제품 데모
- 제품 소개 / 가격 / 문서 / 사례 / FAQ / 온보딩 페이지
- Veridion / ClearPort / GrantOps / DraftForge 제품 상세 페이지
- 외부 결제 진입 및 Toss 결제 승인/실패 처리
- 결제 완료 후 자동 발행 / 결과 팩 생성 / 고객 포털 조회
- 관리자 허브: 주문 / 데모 / 문의 / 발행 / 백업 / 복구 검증
- 자료실 자동 발행 운영
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
자료실 운영만 남기고 판매 축을 끕니다.
- 홈 / 자료실 / 관리자 / 개인정보처리방침만 노출
- 주문 / 결제 / 데모 / 문의 / 포털은 `410 Gone`

전환값:
```bash
NV0_BOARD_ONLY_MODE=0   # 전체판
NV0_BOARD_ONLY_MODE=1   # 자료실 전용판
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
현재 납품본은 `tests/` 디렉터리 대신 `scripts/` 아래 검증 스크립트로 전역 점검을 수행합니다.

전체 검증:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/package_completion_gate.py
```

개별 검증:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/preflight_env.py
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode full
PYTHONPATH=./runtime_vendor python3 scripts/post_deploy_verify.py --base-url http://127.0.0.1:8000 --admin-token "로컬_관리자_토큰"
PYTHONPATH=./runtime_vendor python3 scripts/product_runtime_e2e.py --base-url http://127.0.0.1:8000
PYTHONPATH=./runtime_vendor python3 scripts/veridion_runtime_regression.py --base-url http://127.0.0.1:8000
PYTHONPATH=./runtime_vendor python3 scripts/result_quality_gate.py --base-url http://127.0.0.1:8000
PYTHONPATH=./runtime_vendor python3 scripts/api_safety_regression.py --base-url http://127.0.0.1:8000 --admin-token "로컬_관리자_토큰"
PYTHONPATH=./runtime_vendor python3 scripts/board_mode_regression.py --base-url http://127.0.0.1:8000 --admin-token "로컬_관리자_토큰"
PYTHONPATH=./runtime_vendor python3 scripts/full_audit.py --mode full
PYTHONPATH=./runtime_vendor python3 scripts/full_audit.py --mode board
```

실배포용 deploy 패키지에서 가능한 검증:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/preflight_env.py
PYTHONPATH=./runtime_vendor python3 scripts/package_completion_gate.py
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode full
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode board
PYTHONPATH=./runtime_vendor python3 scripts/post_deploy_verify.py --base-url https://nv0.kr --admin-token "실제_관리자_토큰"
```

배포 후 스모크 테스트:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode full
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode board
```

운영 도메인 배포 후 최종 검증:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/post_deploy_verify.py --base-url https://nv0.kr --admin-token "실제_관리자_토큰"
```

실운영 `.env` 준비:
```bash
cp .env.production.example .env
# 실제 토큰/시크릿/도메인 값으로 교체 후 배포
```

최종 납품 패키지 생성:
```bash
# 검토/감사용 전체 패키지
PYTHONPATH=./runtime_vendor python3 scripts/create_delivery_package.py --mode full

# 실배포용 비밀값 제외 패키지
PYTHONPATH=./runtime_vendor python3 scripts/create_delivery_package.py --mode deploy
```

주의:
- `.env` 는 패키지에 포함되지 않습니다. 배포 서버에서 `.env.production.example` 또는 `.env.example` 을 복사해 실제 값으로 채워 넣으세요.
- `deploy` 모드는 테스트 산출물, 감사 DB, 로컬 실행 로그를 제외한 비밀값 안전 패키지입니다.
- 운영 배포 기본값은 `NV0_STRICT_STARTUP=1` 입니다. 필수값이 비어 있으면 부팅하지 않고 즉시 실패합니다.

## Docker / Coolify
- `Dockerfile` 포함
- `compose.coolify.yaml` 포함
- `/app/data`, `/app/backups` 영구 볼륨 사용
- 기본 컨테이너는 read-only rootfs 기준으로 설정
- `start_server.py` 가 Dockerfile 단독 배포에서도 환경 누락을 완화해 기동 실패를 줄입니다.
- FastAPI/ Uvicorn 공식 가이드 기준으로 TLS 종료 프록시 뒤 배포를 위해 `UVICORN_PROXY_HEADERS=1`, `FORWARDED_ALLOW_IPS=신뢰 프록시 IP/CIDR 또는 *` 를 기본 노출했습니다.
- 기본값으로 Uvicorn `Server`/`Date` 헤더를 끄고, keep-alive/동시성 상한을 환경변수로 조절할 수 있게 했습니다.
- 스테이징/사전 검증은 `NV0_TOSS_MOCK=1`, 실운영 결제 오픈은 `NV0_TOSS_MOCK=0` + 실제 Toss live 키 설정으로만 진행하세요.
- `compose.coolify.yaml` 은 운영 배포에서 `NV0_STRICT_STARTUP=1` 을 기본값으로 사용해, 키 누락·잘못된 도메인·짧은 토큰 상태로는 부팅하지 않도록 막습니다.

## 실제 상용 검증에서 꼭 남는 3단계
이 패키지는 **코드/페이지/API/자동발행/포털 흐름**까지 모두 검증됐습니다.
다만 실운영 완료로 닫으려면 아래 3가지는 실제 환경에서 마지막으로 확인해야 합니다.

1. **실제 Toss 상용 결제 1회**
2. **실제 Coolify 운영 반영 후 post-deploy 검증 1회**
3. **실제 도메인/SSL 전환 후 canonical/host/health 재검증 1회**

이 항목들은 코드 미완성 때문이 아니라, 외부 결제사·프록시·실도메인 환경이 있어야만 끝나는 단계입니다.

## 납품 문서
- `README_KO.md` : 전체 개요
- `INTEGRATION_MAP.md` : 페이지/API/흐름 맵
- `AUDIT_REPORT_KO.md` : `scripts/full_audit.py` 실행 시 생성되는 감사 요약
- `DELIVERY_RUNBOOK_KO.md` : 실배포/복구/검증 절차
- `COOLIFY_APP_DEPLOYMENT_KO.md` : Coolify Application(Dockerfile) 배포 경로와 롤링 업데이트 대응
- `scripts/` : 빌드·스모크·결제·보안·자료실·감사·Veridion 전용 회귀 검증 스크립트 세트

## 패키지 완료 게이트
```bash
PYTHONPATH=./runtime_vendor python3 scripts/package_completion_gate.py
```
이 스크립트는 문법 검사, full 모드 빌드/실행/스모크/배포 검증, board-only 모드 빌드/실행/스모크/감사, 최종 full 복원까지 한 번에 수행합니다.


## 추가 검증 스크립트
- `scripts/api_safety_regression.py` : 관리자 보호, 잘못된 입력, 중복 결제 승인, 웹훅 중복, 본문 크기 제한 회귀 검증
- `scripts/board_mode_regression.py` : board-only 모드에서 허용/차단 페이지와 API가 기대대로 동작하는지 검증
- `scripts/deployment_consistency_check.py` : compose, Dockerfile, env 예시, 런북/README 참조 스크립트 일치성 검증
