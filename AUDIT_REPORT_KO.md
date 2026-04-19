# NV0 최종 감사 리포트

## 1. 산출물 수량
- 모드: full
- 정적 HTML 페이지 수: 56
- 활성 API route 수: 48
- 소스상 선언 route 수: 52
- 현재 모드 기준 비활성 route 수: 4
- 테스트/검증 스크립트 수: 9
- 소스 TODO/FIXME/XXX 표기 수: 0

## 2. 페이지 목록
- admin/index.html
- auth/index.html
- billing/index.html
- board/index.html
- board/post/index.html
- cases/index.html
- checkout/index.html
- company/index.html
- contact/index.html
- demo/index.html
- docs/clearport/index.html
- docs/draftforge/index.html
- docs/grantops/index.html
- docs/index.html
- docs/veridion/index.html
- engine/index.html
- faq/index.html
- guides/index.html
- index.html
- legal/cookies/index.html
- legal/privacy/index.html
- legal/refund/index.html
- modules/index.html
- onboarding/index.html
- payments/toss/fail/index.html
- payments/toss/success/index.html
- portal/index.html
- pricing/index.html
- products/clearport/board/index.html
- products/clearport/delivery/index.html
- products/clearport/demo/index.html
- products/clearport/faq/index.html
- products/clearport/index.html
- products/clearport/plans/index.html
- products/draftforge/board/index.html
- products/draftforge/delivery/index.html
- products/draftforge/demo/index.html
- products/draftforge/faq/index.html
- products/draftforge/index.html
- products/draftforge/plans/index.html
- products/grantops/board/index.html
- products/grantops/delivery/index.html
- products/grantops/demo/index.html
- products/grantops/faq/index.html
- products/grantops/index.html
- products/grantops/plans/index.html
- products/index.html
- products/veridion/board/index.html
- products/veridion/delivery/index.html
- products/veridion/demo/index.html
- products/veridion/faq/index.html
- products/veridion/index.html
- products/veridion/plans/index.html
- resources/index.html
- service/index.html
- solutions/index.html

## 3. 활성 API 목록
- GET /healthz
- GET /health
- GET /livez
- GET /live
- GET /readyz
- GET /ready
- GET /api/health
- GET /admin/index.html
- GET /admin/
- GET /admin
- GET /admin/login/index.html
- GET /admin/login/
- GET /admin/login
- POST /admin/login
- POST /api/admin/login
- POST /api/admin/logout
- GET /api/admin/session
- GET /api/admin/health
- GET /api/public/system-config
- GET /api/admin/validate
- GET /api/admin/state
- GET /api/admin/export
- POST /api/admin/import
- GET /api/public/board/feed
- POST /api/public/orders
- POST /api/public/orders/reserve
- POST /api/public/payments/toss/confirm
- POST /api/public/orders/{order_id}/intake
- POST /api/public/payments/toss/webhook
- POST /api/public/veridion/scan
- POST /api/public/clearport/analyze
- POST /api/public/grantops/analyze
- POST /api/public/draftforge/analyze
- POST /api/public/demo-requests
- POST /api/public/contact-requests
- POST /api/public/portal/lookup
- POST /api/public/auth/register
- POST /api/public/auth/login
- POST /api/public/auth/logout
- GET /api/public/auth/me
- POST /api/public/portal/history
- GET /api/admin/board-settings
- POST /api/admin/board-settings
- POST /api/admin/library/publications
- POST /api/admin/library/assets
- POST /api/admin/actions/publish-now
- POST /api/admin/actions/reseed-board
- POST /api/admin/actions/reset

## 4. 현재 모드에서 비활성 처리되는 route
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
- 즉시 시연 / 결제 진입 / 자동 발행 / 포털 확인 흐름은 코드 및 로컬 검증 기준 완료
- 실제 상용 결제는 실키 환경에서 마지막 1회만 추가 확인 필요
