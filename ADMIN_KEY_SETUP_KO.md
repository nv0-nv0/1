# 관리자 키 설정 방법

## 1) 로컬 개발
1. 프로젝트 루트에서 `.env.example` 를 복사해 `.env` 를 만듭니다.
2. `NV0_ADMIN_TOKEN` 값을 32자 이상 랜덤 문자열로 바꿉니다.
3. 서버를 다시 시작합니다.

예시:
```env
NV0_ADMIN_TOKEN=nv0-admin-2026-change-this-to-a-long-random-string
NV0_REQUIRE_ADMIN_TOKEN=1
```

## 2) 운영 배포(Coolify 권장)
1. 프로젝트 또는 서비스 설정으로 들어갑니다.
2. **Environment Variables** 메뉴를 엽니다.
3. 아래 값을 추가 또는 수정합니다.
   - `NV0_ADMIN_TOKEN` = 32자 이상 랜덤 관리자 키
   - `NV0_REQUIRE_ADMIN_TOKEN` = `1`
4. 저장 후 **Redeploy / Restart** 합니다.

## 3) 로그인 방법
- 배포 후 `/admin` 또는 `/admin/index.html` 로 이동합니다.
- 방금 넣은 `NV0_ADMIN_TOKEN` 값을 입력하면 됩니다.
- 로그인 성공 시 HttpOnly 관리자 세션 쿠키가 발급됩니다.

## 4) 안전 권장값
- 영문 대소문자 + 숫자 + 특수문자 혼합
- 32자 이상
- Toss 키, 백업 암호와 다른 값 사용
- 운영/스테이징 분리

## 5) 빠른 생성 예시
터미널에서 생성:
```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(36))
PY
```

## 6) 확인 포인트
- `.env.production.example` 에도 동일 키 이름이 정의되어 있습니다.
- `NV0_STRICT_STARTUP=1` 인 운영 배포에서는 관리자 키가 짧거나 비어 있으면 부팅이 차단됩니다.
