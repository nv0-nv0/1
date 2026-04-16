# NV0 게시판 전용 감사 리포트

## 1. 산출물 수량
- 모드: board
- 정적 HTML 페이지 수: 5
- 활성 API route 수: 17
- 소스상 선언 route 수: 32
- 현재 모드 기준 비활성 route 수: 15
- 테스트/검증 스크립트 수: 9
- 소스 TODO/FIXME/XXX 표기 수: 0

## 2. 페이지 목록
- admin/index.html
- board/index.html
- board/post/index.html
- index.html
- legal/privacy/index.html

## 3. 활성 API 목록
- GET /healthz
- GET /health
- GET /livez
- GET /live
- GET /readyz
- GET /ready
- GET /api/health
- GET /api/admin/health
- GET /api/public/system-config
- GET /api/admin/validate
- GET /api/admin/state
- GET /api/admin/export
- POST /api/admin/import
- GET /api/public/board/feed
- POST /api/admin/actions/publish-now
- POST /api/admin/actions/reseed-board
- POST /api/admin/actions/reset

## 4. 현재 모드에서 비활성 처리되는 route
- POST /api/public/orders
- POST /api/public/orders/reserve
- POST /api/public/payments/toss/confirm
- POST /api/public/payments/toss/webhook
- POST /api/public/veridion/scan
- POST /api/public/clearport/analyze
- POST /api/public/grantops/analyze
- POST /api/public/draftforge/analyze
- POST /api/public/demo-requests
- POST /api/public/contact-requests
- POST /api/public/portal/lookup
- POST /api/admin/actions/seed-demo
- POST /api/admin/orders/{order_id}/advance
- POST /api/admin/orders/{order_id}/toggle-payment
- POST /api/admin/orders/{order_id}/republish

## 5. 테스트 및 검증 목록
- scripts/api_safety_regression.py
- scripts/board_mode_regression.py
- scripts/deployment_consistency_check.py
- scripts/package_completion_gate.py
- scripts/post_deploy_verify.py
- scripts/preflight_env.py
- scripts/product_runtime_e2e.py
- scripts/result_quality_gate.py
- scripts/smoke_release.py

## 6. 외부 환경이 필요한 최종 확인
- 1. 실제 Toss 실결제
- 2. 실제 Coolify 운영 반영
- 3. 실제 도메인/SSL 운영 전환

## 7. 판정
- 게시판 전용 운영 범위와 410 차단 정책은 검증 완료
