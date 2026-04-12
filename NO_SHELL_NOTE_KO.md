# 납품 패키지 구성 안내

이 패키지는 껍데기형 축소본이 아니라 다음을 포함한 통짜 납품본입니다.

- 전체 소스(`src/`)
- 전체 산출물(`dist/`)
- 서버(`server_app.py`)
- 테스트/스크립트/배포 설정
- 데이터베이스 샘플(`data/nv0.db`)
- 원본 호환 자산(`server_app.py.bak`, `FULL_PACKAGE_MANIFEST.json`, `.venvcheck/`)
- 로컬 런타임 번들(`runtime_vendor/`)

`runtime_vendor/`에는 FastAPI/Uvicorn/Requests 및 실제 실행 의존성이 포함되어 있습니다.

빠른 실행:

```bash
./run_with_vendor.sh
```

빠른 검증:

```bash
./test_with_vendor.sh
```
