# NV0 납품/배포 런북

## 1. 가장 먼저 할 일
1. `.env.example`를 복사해 실제 환경변수 입력
2. `NV0_BOARD_ONLY_MODE=0` 확인
3. `NV0_TOSS_MOCK=1`로 먼저 스테이징 점검 (기본 권장값)
4. `PYTHONPATH=./runtime_vendor python3 scripts/package_completion_gate.py` 실행
5. `PYTHONPATH=./runtime_vendor python3 scripts/create_delivery_package.py`로 납품 패키지 생성

## 2. Coolify/컨테이너 운영 기본값
필수:
- `NV0_BASE_URL`
- `NV0_ALLOWED_HOSTS`
- `NV0_ALLOWED_ORIGINS`
- `NV0_ADMIN_TOKEN`
- `NV0_BACKUP_PASSPHRASE`
- `NV0_DATA_DIR=/app/data`
- `NV0_BACKUP_DIR=/app/backups`
- `NV0_BOARD_ONLY_MODE=0`
- `NV0_PAYMENT_PROVIDER=toss`
- `NV0_STRICT_STARTUP=1` (운영 기본값, 필수값이 비면 즉시 실패)
- `UVICORN_PROXY_HEADERS=1`
- `FORWARDED_ALLOW_IPS=신뢰 프록시 IP/CIDR 또는 *`
- `UVICORN_SERVER_HEADER=0`
- `UVICORN_DATE_HEADER=0`

테스트 결제:
- `NV0_TOSS_MOCK=1` (기본 권장값)

실결제:
- `NV0_TOSS_CLIENT_KEY`
- `NV0_TOSS_SECRET_KEY`
- `NV0_TOSS_WEBHOOK_SECRET`
- `NV0_TOSS_MOCK=0`

## 3. 배포 전 체크
```bash
PYTHONPATH=./runtime_vendor python3 scripts/preflight_env.py
PYTHONPATH=./runtime_vendor python3 build.py
PYTHONPATH=./runtime_vendor python3 scripts/package_completion_gate.py
PYTHONPATH=./runtime_vendor python3 scripts/deployment_consistency_check.py
```

## 4. 배포 직후 스모크 테스트
### full mode
```bash
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url https://your-domain.example --mode full
```

### board-only mode
```bash
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url https://your-domain.example --mode board
```

관리자 확인 포함:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url https://your-domain.example --mode full --admin-token 'YOUR_ADMIN_TOKEN'
```

## 5. 실결제 전환 절차
1. 스테이징/운영에서 `NV0_TOSS_MOCK=1`로 전체 흐름 확인
2. 실키 입력
3. `NV0_TOSS_MOCK=0` 전환
4. 소액 1회 결제
5. success 페이지 복귀 확인
6. 주문 상태 `paid/published` 확인
7. 포털 조회로 결과 팩 확인
8. 웹훅 재전송 시 중복 발행 없는지 확인

## 6. 백업/복구
백업 생성:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/backup_state.py --base-url https://your-domain.example --admin-token 'YOUR_ADMIN_TOKEN' --passphrase 'YOUR_BACKUP_PASSPHRASE'
```

verify-only 복구 검증:
```bash
PYTHONPATH=./runtime_vendor python3 scripts/restore_state.py /path/to/backup.tar.gz.enc --passphrase 'YOUR_BACKUP_PASSPHRASE' --verify-only
```

## 7. 문제가 생기면 먼저 볼 것
- `GET /api/health`
- `GET /api/public/system-config`
- 호스트/오리진 설정
- 관리자 토큰 길이/누락
- Toss mock/live 전환값
- `/app/data`, `/app/backups` 쓰기 가능 여부

## 8. 납품본 구성 확인
- 최종 ZIP/TAR
- `PACKAGE_CONTENTS.txt`
- `PACKAGE_CONTENTS.json`
- `SHA256SUMS.txt`
- 본 런북
- README / 통합 맵 / 감사 보고서(필요 시 생성) / 테스트 세트

## 패키지 완료 게이트
```bash
PYTHONPATH=./runtime_vendor python3 scripts/package_completion_gate.py
```
이 스크립트는 문법 검사, full 모드 빌드/실행/스모크/배포 검증, board-only 모드 빌드/실행/스모크/감사, 최종 full 복원까지 한 번에 수행합니다.


## 추가 검증 스크립트
- `scripts/api_safety_regression.py` : 관리자 보호, 잘못된 입력, 중복 결제 승인, 웹훅 중복, 본문 크기 제한 회귀 검증
- `scripts/board_mode_regression.py` : board-only 모드에서 허용/차단 페이지와 API가 기대대로 동작하는지 검증
- `scripts/deployment_consistency_check.py` : compose, Dockerfile, env 예시, 런북/README 참조 스크립트 일치성 검증
