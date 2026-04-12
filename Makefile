.PHONY: build test run preflight release smoke-full smoke-board

build:
	python3 build.py

test:
	python3 tests/test_all.py

run:
	python3 -m uvicorn server_app:app --host 0.0.0.0 --port 8000

preflight:
	python3 scripts/preflight_env.py

release:
	python3 scripts/create_delivery_package.py

smoke-full:
	python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode full

smoke-board:
	python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode board
