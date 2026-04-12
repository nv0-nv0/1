# NV0 full recovery report — 2026-04-12

## What was restored
- Full-mode build by default (`NV0_BOARD_ONLY_MODE=0` default)
- Product pages restored, including `products/veridion/index.html`
- Immediate demo flow restored on product pages
- Checkout, portal, docs, pricing, cases, FAQ, contact, payment result pages restored
- Public order/payment/demo/contact/portal APIs restored in full mode
- Admin seed/advance/toggle-payment/republish APIs restored in full mode
- Board-only mode preserved behind `NV0_BOARD_ONLY_MODE=1`
- Deployment env updated to expose `NV0_BOARD_ONLY_MODE`

## Key behavior verified
- `GET /products/veridion/` returns product detail with demo/order/payment/delivery sections
- `POST /api/public/orders/reserve` creates a ready Toss order
- `POST /api/public/payments/toss/confirm` marks payment paid and auto-publishes deliverables/publications
- `POST /api/public/portal/lookup` returns the order and linked publications
- Demo/contact/admin workflows operate in full mode
- Board-only build and board-only API scope still work when enabled

## Important deployment note
- Real external Toss payment requires valid `NV0_TOSS_CLIENT_KEY` and `NV0_TOSS_SECRET_KEY`
- End-to-end verification in this report used `NV0_TOSS_MOCK=1`
- With real Toss keys set and mock disabled, the same flow is ready to use against Toss

## Test results
- `tests/full_api_e2e_check.py` → PASS
- `tests/api_deploy_check.py` → PASS
- `tests/content_integrity_check.py` → PASS
- `tests/board_only_scope_check.py` → PASS
- `tests/packaging_runtime_check.py` → PASS
- `tests/runtime_engine_check.js` → PASS

## Files changed
- `build.py`
- `server_app.py`
- `src/assets/site.js`
- `src/data/site.json`
- `scripts/generate_compat_pages.py`
- `compose.coolify.yaml`
- `.env.example`
- `tests/full_api_e2e_check.py`
- `tests/content_integrity_check.py`
- `tests/packaging_runtime_check.py`
- `tests/board_only_scope_check.py`
- `tests/runtime_engine_check.js`
- `tests/test_all.py`
