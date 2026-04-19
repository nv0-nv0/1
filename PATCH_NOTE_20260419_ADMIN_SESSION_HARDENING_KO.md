# 2026-04-19 관리자 인증/데모 추가 보강 내역

## 이번 보강 핵심
- 관리자 키 입력 후 다시 키를 요구하던 흐름을 재설계했습니다.
- 쿠키가 브라우저/프록시/로컬 환경에서 흔들려도 관리자 헤더 인증으로 즉시 복구되도록 보강했습니다.
- 관리자 키를 세션 저장소만이 아니라 로컬 저장소에도 보존해 새로고침/재진입 시 메뉴가 바로 열리도록 보강했습니다.
- `/api/admin/session` 이 쿠키 인증뿐 아니라 `X-Admin-Token` 헤더 인증도 받아들이고, 헤더 인증 성공 시 세션 쿠키를 즉시 재발급하도록 수정했습니다.
- `/api/admin/state`, `/api/admin/validate` 호출 시 저장된 실제 관리자 키를 함께 보내도록 프런트 로직을 수정했습니다.

## 수정 파일
- `server_app.py`
- `src/assets/site.js`
- `dist/assets/site.js`
- `PATCH_NOTE_20260419_ADMIN_SESSION_HARDENING_KO.md`

## 직접 확인한 항목
- `python -m py_compile server_app.py start_server.py`
- `node --check dist/assets/site.js`
- `node --check src/assets/site.js`
- `python scripts/smoke_release.py --base-url http://127.0.0.1:8123 --mode full --admin-token ...` 통과
- 관리자 로그인 후 쿠키 인증 확인
- 헤더만 있는 상태에서 `/api/admin/session` 성공 및 세션 쿠키 재발급 확인
- 헤더만 있는 상태에서 `/api/admin/state` 성공 확인

## 기대되는 효과
- 관리 키 입력 후 메뉴 없이 빈 화면/재로그인 루프 감소
- 로컬 실행, 프록시 환경, 쿠키 반영 지연 환경에서 관리자 진입 안정성 향상
- 데모/주문/관리 상태 동기화 실패 시 복구성 강화
