# Veridion 최종 납품 보고서 (2026-04-16)

## 1) 이번 반영 목적
- 공개 홈/제품/게시판을 Veridion 단일 서비스 중심으로 재정렬
- 다른 제품은 분리 모듈 허브로 분리 유지
- 상단 메뉴/좌측 네비/관계자 진입 구조 유지
- 배포 시 소스와 dist 불일치가 다시 생기지 않도록 Docker 이미지 빌드 단계에서 정적 산출물 재생성 강제

## 2) 실제 변경한 파일
- `src/data/site.json`
- `build.py`
- `src/assets/site.js`
- `scripts/page_overrides.py`
- `Dockerfile`
- `dist/*` 재생성

## 3) 실제 변경 내용
### 공개 구조
- 홈을 Veridion 중심 랜딩으로 변경
- 제품 페이지를 Veridion 공개 판매 허브로 재정렬
- 게시판을 Veridion 자동발행 게시판으로 재정렬
- `modules/index.html` 신규 생성
- 분리 모듈( ClearPort / GrantOps / DraftForge )은 공개 홈 전면 노출 대신 모듈 허브로 분리

### 데이터/카피
- 브랜드/메인 카피를 Veridion 중심으로 갱신
- 공개 게시판 seed 데이터를 Veridion 중심으로 재정렬
- 회사 소개의 운영 원칙을 “공개 단순화 / 운영 분리 / Veridion 집중” 방향으로 갱신

### 프런트 동작
- 홈 카드 렌더링을 Veridion 1개 공개 중심으로 변경
- 모듈 매트릭스는 Veridion 제외 모듈만 렌더링하도록 변경
- 공개 게시판은 Veridion 글만 우선 렌더링하도록 변경
- `/modules/` 경로를 제품 허브 활성 영역으로 인식하도록 네비 상태 로직 보강

### 배포 안정성
- Dockerfile에 `RUN python build.py` 추가
- 이미지 빌드 시 최신 소스를 기준으로 `dist`를 강제 재생성하도록 변경
- 소스 수정 후 예전 dist가 그대로 배포되는 회귀 리스크를 낮춤

## 4) 실제 확인 완료
### 정적/문법
- `python -m py_compile build.py server_app.py start_server.py scripts/*.py`
- `node --check src/assets/site.js`
- `python build.py`

### 서버/스모크
- `scripts/preflight_env.py`
- `scripts/smoke_release.py --mode full`
- `scripts/post_deploy_verify.py`

### 기능/E2E/회귀
- `scripts/product_runtime_e2e.py`
- `scripts/veridion_runtime_regression.py`
- `scripts/product_surface_regression.py`
- `scripts/runtime_hardening_regression.py`
- `scripts/result_quality_gate.py`
- `scripts/automation_runtime_regression.py`
- `scripts/api_safety_regression.py`
- `scripts/deployment_consistency_check.py`

## 5) 핵심 검증 결과
- 공개 홈/제품/게시판 정적 산출물 재생성 확인
- `/modules/index.html` 생성 확인
- Veridion 데모 → 주문 → 결제 확인 → 포털 조회 흐름 통과
- 4개 제품 전체 런타임 E2E 통과
- Veridion 리포트 생성/발행/전달 자산 확인
- 품질 게이트 점수 100 확인
- 관리 화면 수동 위험 버튼 비노출 확인
- 배포 일관성 검사 통과

## 6) 남은 리스크
- 실제 운영 도메인 반영은 Git 반영 후 재배포가 필요
- 실결제 Toss live 키 운영 검증은 별도
- 외부 실제 사이트의 크롤링 품질은 robots/차단 정책에 따라 달라질 수 있음
- 브라우저 캐시가 남아 있으면 구버전 화면이 보일 수 있음

## 7) 배포 시 바로 볼 체크포인트
- `/`
- `/products/`
- `/board/`
- `/modules/`
- `/auth/`
- `/admin/`

## 8) 판단
- 로컬 기준 검토 가능: 예
- 로컬 기준 시연 가능: 예
- 인수 검토 가능: 예
- 패키지 납품 가능: 예
- 운영 도메인 최종 반영 확인: 재배포 후 확인 필요
