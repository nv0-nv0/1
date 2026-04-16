# Veridion 재전수 검토 및 재납품 보고서

## 1. 이번 재검토 목적
- 소스/정적 산출물/Docker/핵심 API/공개 페이지/보드 전용 모드까지 다시 점검
- 공개 홈/제품/게시판/회사소개/로그인(회원가입)/관계자 노출 구조를 재확인
- 배포 시 `dist` 회귀 가능성과 JS 단독 렌더 의존성을 추가 보강

## 2. 실제로 보강한 항목
- `Dockerfile`의 `python build.py` 강제 빌드 유지
- 상단 메뉴/좌측 네비/관계자 버튼을 **정적 HTML에도 기본 출력**하도록 보강
- JS는 정적 네비를 다시 동기화하는 방식으로 유지
- `renderSidebar()`를 기존 노드가 있어도 갱신하도록 수정
- 모바일 드로어 생성 로직 유지
- full / board-only 빌드 모두 재생성

## 3. 이번 재검토에서 실제 확인 완료
### 정적/빌드
- `node --check src/assets/site.js`
- `python -m py_compile build.py server_app.py start_server.py scripts/*.py`
- `python build.py` (full)
- `python build.py` (board-only)
- full 빌드 결과 HTML에 `관계자`, `회사소개`, `로그인(회원가입)`, `게시판(자동발행)`, `side-nav-shell` 정적 출력 확인

### full mode 런타임
- `scripts/smoke_release.py --mode full`
- `scripts/post_deploy_verify.py --skip-www-redirect`
- `scripts/product_runtime_e2e.py`
- `scripts/veridion_runtime_regression.py`
- `scripts/product_surface_regression.py`
- `scripts/runtime_hardening_regression.py`
- `scripts/result_quality_gate.py`
- `scripts/automation_runtime_regression.py`
- `scripts/api_safety_regression.py`
- `scripts/deployment_consistency_check.py`

### board-only mode 런타임
- `scripts/smoke_release.py --mode board`
- `scripts/board_mode_regression.py`

## 4. 확인된 핵심 결과
- full mode: 홈/제품/게시판/회사소개/로그인/관리자/포털/결제 성공 shell 정상 응답
- Veridion 데모 → 주문 → mock 결제 승인 → 발행 → 포털 조회 정상
- 4개 제품 전체 런타임 E2E 정상
- 품질 게이트 점수 100 확인
- 자동화 UI에서 수동 위험 버튼 비노출 확인
- 보안 회귀: admin auth guard / invalid host guard / body-size guard / payment idempotency / duplicate webhook guard 통과
- board-only mode: 허용 표면만 200, 비허용 페이지와 API는 제한 동작 확인

## 5. 남은 리스크
- Toss 실결제 live 키 운영 검증은 별도
- 실제 운영 도메인 재배포 후 CDN/브라우저 캐시 영향은 별도 확인 필요
- 관리자 내부 전체 수동 운영 UX를 브라우저 E2E로 끝까지 검증한 것은 아님

## 6. 납품 판단
- 로컬 기준 검토 가능: 예
- 로컬 기준 시연 가능: 예
- 로컬 기준 인수 검토 가능: 예
- 로컬 기준 납품 가능: 예
- 운영 도메인 최종 닫힘 조건: 최신 소스 Git 반영 후 재배포 + 운영 도메인 smoke/post-deploy 1회
