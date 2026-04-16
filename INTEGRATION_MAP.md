# NV0 통합 맵

## 1. 사용자 흐름
1. 홈 또는 제품 페이지 진입
2. 제품 상세에서 즉시 데모 실행
3. 같은 페이지 또는 체크아웃에서 결제 진입
4. 외부 결제 완료 후 success 페이지 복귀
5. 서버가 주문을 paid/published로 전환
6. 결과 팩 생성 및 자동발행 게시글 연결
7. 고객 포털에서 이메일 + 조회 코드로 납품 확인

## 2. 제품 축
- Veridion
- ClearPort
- GrantOps
- DraftForge

## 3. 공개 페이지
### full mode
- 홈: `/`
- 제품 목록: `/products/`
- 제품 상세: `/products/{product}/`
- 제품별 보드: `/products/{product}/board/`
- 가격: `/pricing/`
- 사례: `/cases/`
- 문서: `/docs/`
- FAQ: `/faq/`
- 데모: `/demo/`
- 체크아웃: `/checkout/`
- 문의: `/contact/`
- 포털: `/portal/`
- 결제 성공/실패: `/payments/toss/success/`, `/payments/toss/fail/`
- 게시판: `/board/`
- 관리자: `/admin/`
- 법적 문서: `/legal/privacy/`, `/legal/refund/`

### board-only mode
- `/`
- `/board/`
- `/admin/`
- `/legal/privacy/`

## 4. API 매트릭스
### 항상 활성
- `GET /api/health`
- `GET /api/admin/health`
- `GET /api/public/system-config`
- `GET /api/public/board/feed`
- `GET /api/admin/validate`
- `GET /api/admin/state`
- `GET /api/admin/export`
- `POST /api/admin/import`
- `POST /api/admin/actions/publish-now`
- `POST /api/admin/actions/reseed-board`
- `POST /api/admin/actions/reset`

### full mode 전용
- `POST /api/public/demo-requests`
- `POST /api/public/contact-requests`
- `POST /api/public/orders`
- `POST /api/public/orders/reserve`
- `POST /api/public/payments/toss/confirm`
- `POST /api/public/payments/toss/webhook`
- `POST /api/public/portal/lookup`
- `POST /api/admin/actions/seed-demo`
- `POST /api/admin/orders/{order_id}/republish`
- `POST /api/admin/orders/{order_id}/advance`
- `POST /api/admin/orders/{order_id}/toggle-payment`

### board-only mode 응답 정책
- 판매/결제/포털 관련 경로는 `410 Gone`

## 5. 저장 축
### full mode
- orders
- demos
- contacts
- lookups
- publications
- webhook_events
- scheduler

### board-only mode
- publications
- scheduler

## 6. 결제/발행 관계
- reserve/order 생성 → `payment_pending`
- Toss confirm/webhook 성공 → `paid`
- publish 엔진 연결 → `published`
- 관리자 advance 또는 흐름 완료 → `delivered`

## 7. 운영 안전장치
- 관리자 토큰 검증
- 호스트/오리진 허용 목록 검증
- rate limit
- body size 제한
- 백업 생성 및 verify-only 복구 검증
- 결제 confirm/webhook 중복 처리 방지
- 중복 발행 방지
- board-only 모드 경로 차단
