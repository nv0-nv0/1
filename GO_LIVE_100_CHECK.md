# NV0 100% 선언용 최종 운영 확인

이 패키지는 코드와 패키지 기준으로 완성되어 있습니다.

실운영에서 100% 완료 선언을 하려면 아래 1개 명령만 실제 도메인에 대해 통과시키면 됩니다.

```bash
python3 scripts/post_deploy_verify.py --base-url https://nv0.kr --admin-token "$NV0_ADMIN_TOKEN"
```

통과 기준:
- 홈/제품/가격/문서/게시판/데모/체크아웃/포털 응답 200
- 4개 제품 상세/게시판/문서 응답 200
- `/api/health` 정상
- `www.nv0.kr -> nv0.kr` canonical redirect 정상
- 데모 저장 정상
- 문의 저장 정상
- 주문 reserve 정상
- Toss confirm(mock/운영 환경 정책에 따른 실제 응답) 정상
- 포털 조회 정상
- 관리자 state 정상

성공 시 출력:
- `POST_DEPLOY_VERIFY_OK`

이 성공 마커가 실도메인에서 확인되면 운영 기준 100% 완료 선언이 가능합니다.
