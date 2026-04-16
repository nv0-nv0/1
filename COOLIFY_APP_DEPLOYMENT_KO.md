# NV0 Coolify Application 배포 가이드

## 왜 이 경로를 같이 넣었는가
Coolify 공식 문서 기준으로 **Docker Compose 기반 배포는 Rolling Updates를 지원하지 않습니다.**
반면 Application(Dockerfile) 배포는 정상 health check가 있을 때 배포 동선을 더 단순하게 가져가기 좋습니다.

따라서 NV0는 두 경로를 같이 제공합니다.
- `compose.coolify.yaml` : 메인 서비스 + 백업 사이드카를 한 번에 올리는 운영형 스택
- `Dockerfile` 기반 Application 배포 : 롤링 업데이트와 단순 운영을 우선할 때 권장

## 권장 운영안
1. **운영 서비스는 Coolify Application + Dockerfile** 로 배포
2. `/readyz` health check 사용
3. 아래 환경변수를 Coolify UI에 입력
   - `NV0_BASE_URL`
   - `NV0_ALLOWED_HOSTS`
   - `NV0_ALLOWED_ORIGINS`
   - `NV0_ADMIN_TOKEN`
   - `NV0_BACKUP_PASSPHRASE`
   - `NV0_TOSS_CLIENT_KEY` / `NV0_TOSS_SECRET_KEY` / `NV0_TOSS_WEBHOOK_SECRET`
   - `NV0_TOSS_MOCK`
   - `UVICORN_PROXY_HEADERS=1`
   - `FORWARDED_ALLOW_IPS=신뢰 프록시 IP/CIDR 또는 *`
   - `UVICORN_SERVER_HEADER=0`
   - `UVICORN_DATE_HEADER=0`
4. 백업은 Coolify Scheduled Command 또는 외부 크론으로 실행

## 백업 스케줄 예시
```bash
python scripts/backup_state.py --base-url https://nv0.kr --admin-token "$NV0_ADMIN_TOKEN" --passphrase "$NV0_BACKUP_PASSPHRASE"
```

## 배포 직후 검증
```bash
PYTHONPATH=./runtime_vendor python3 scripts/post_deploy_verify.py --base-url https://nv0.kr --admin-token "$NV0_ADMIN_TOKEN"
```

## 주의
- compose 경로를 유지하면 사이드카 백업을 같이 가져가기 쉽지만, Coolify 공식 문서 기준 Rolling Updates 자체는 기대하지 않는 편이 안전합니다.
- 배포 단순성·재기동 안정성·업데이트 안정성을 더 우선하면 Dockerfile Application 배포가 더 낫습니다.
