.PHONY: build test run preflight release smoke-full smoke-board package-check

build:
	python3 build.py

test:
	@if [ -f tests/test_all.py ]; then 		PYTHONPATH=./runtime_vendor:./tests python3 tests/test_all.py; 	else 		echo "tests/ 세트는 deploy 패키지에 포함되지 않습니다. 전체 검증은 full/audit 패키지에서 실행하세요."; 		echo "대신 이 패키지에서는 make preflight 후, 실행 중인 서버에 대해 make smoke-full 또는 make smoke-board 를 사용하세요."; 	fi

run:
	python3 start_server.py

preflight:
	PYTHONPATH=./runtime_vendor python3 scripts/preflight_env.py

release:
	PYTHONPATH=./runtime_vendor python3 scripts/create_delivery_package.py

smoke-full:
	PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode full

smoke-board:
	PYTHONPATH=./runtime_vendor python3 scripts/smoke_release.py --base-url http://127.0.0.1:8000 --mode board

package-check:
	@if [ -f tests/packaging_runtime_check.py ]; then 		PYTHONPATH=./runtime_vendor:./tests python3 tests/packaging_runtime_check.py; 	else 		echo "packaging_runtime_check 는 full/audit 패키지에서 실행하세요."; 	fi
