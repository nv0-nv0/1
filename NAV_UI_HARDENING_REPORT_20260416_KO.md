# Veridion 네비게이션·인증 UI 보강 보고서

## 실제 반영 완료
- 상단 메뉴를 `홈 / 제품 / 게시판 / 회사소개 / 로그인(회원가입)` 구조로 고정
- 제품 서브 메뉴를 `안내 / 가격 / 게시판(자동발행)` 구조로 고정
- 좌측 고정 네비게이션 실제 렌더링 호출 추가
- 좌측 상단 관계자 버튼 유지 및 모바일 드로어에도 동일 반영
- 모바일 메뉴 토글, 드로어, 백드롭, 닫기 동작 추가
- `auth/index.html` 페이지를 빌드 산출물에 다시 포함하도록 빌드 스크립트 보강
- 로그인/회원가입 페이지 라우트 실제 복구

## 실제 확인 완료
- `python -m py_compile server_app.py build.py start_server.py`
- `node --check src/assets/site.js`
- `node --check dist/assets/site.js`
- `GET /`
- `GET /products/veridion/index.html`
- `GET /auth/index.html`
- `POST /api/public/auth/register`
- `POST /api/public/auth/login`

## 동작 확인 필요
- 실제 브라우저 렌더링 기준 최종 간격·정렬 미세 조정
- 모바일 실기기에서 드로어 체감 확인

## 검증 미완료
- 실결제 운영 키 기준 전체 회귀
- 관리자 전체 화면 UX 전역 회귀
