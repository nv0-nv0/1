# NV0 Rework Audit and Delivery Note (2026-04-12)

## What changed
- Home page strengthened from thin landing copy to a clearer company + common engine + module structure.
- Added distinct `/engine/` page instead of reusing the products page.
- Added distinct `/solutions/` page for problem-first navigation.
- Product detail pages now include server-rendered product names, headlines, value points, outputs, demo guidance, pricing basis, plan cards, related modules, and FAQ before JavaScript runs.
- Navigation updated to expose the engine and board more clearly.
- Content integrity tests strengthened to verify the new structure.

## Verified locally
- `python3 tests/test_all.py`
- `python3 tests/robustness_check.py`
- `python3 tests/packaging_runtime_check.py`

## Important limitation
- This package has **not** been deployed to the real `nv0.kr` server in this environment.
- Live production behavior still requires server-side deployment, DNS/proxy confirmation, and post-deploy smoke testing.
