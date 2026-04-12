이 디렉터리는 FastAPI/Uvicorn/Requests 및 런타임 의존성을 로컬에 포함한 오프라인 실행용 번들입니다.
기본 실행 예: PYTHONPATH=./runtime_vendor python3 server_app.py
검증 예: PYTHONPATH=./runtime_vendor python3 tests/test_all.py
