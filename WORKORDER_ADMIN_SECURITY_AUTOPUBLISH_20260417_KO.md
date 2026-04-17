# NV0 관리자 보안·자동발행 작업지시서 및 처리 결과

## 1. 목표
- 공개 URL만 알아도 관리자 구조와 설정 화면이 노출되는 문제 차단
- 브라우저 저장 토큰 방식 대신 서버 검증 + 보안 쿠키 세션으로 관리자 인증 전환
- 자동발행을 주기/빈도 중심 설정형으로 확장
- 기존 자료실 자동 발행 흐름을 유지하면서 즉시 발행/스케줄 발행을 모두 지원

## 2. 핵심 문제
1. `/admin/index.html`에 비인증 사용자가 직접 접근 가능
2. 관리자 키 입력 UI와 메뉴 구조가 HTML에 먼저 노출
3. 클라이언트 세션스토리지 토큰 의존
4. 관리자 API가 프런트 토큰 전송 구조에 치우쳐 있음
5. 자동발행 설정이 CTA 중심으로만 되어 있어 주기·빈도 운영이 어려움

## 3. 적용 지시 사항
### 보안
- 비인증 사용자는 `/admin`, `/admin/`, `/admin/index.html` 접속 시 로그인 HTML만 받도록 변경
- 로그인 성공 시 `HttpOnly` 관리자 세션 쿠키 발급
- 관리자 HTML 및 `/api/admin/*`는 세션 또는 서버 검증 토큰으로만 접근 허용
- 관리자 로그인/로그아웃/세션 확인 API 추가
- 관리자 페이지와 관련 API에 `noindex, nofollow`, `no-store` 적용 유지

### 자동발행
- 자동발행 on/off
- 주기: `daily | weekly | interval`
- 빈도: `frequencyPerRun`
- 시간대: `timeSlots`
- interval 기준 시간: `intervalHours`
- 대상 제품 선택: `selectedProducts`
- 발행 모드: `publish | draft` 저장
- 즉시 발행 버튼 유지

## 4. 실제 반영 파일
- `server_app.py`
- `dist/assets/site.js`
- `src/assets/site.js`
- `dist/admin/index.html`

## 5. 구현 결과 요약
### 관리자 보안
- `/admin/index.html` 비인증 접근 시 관리자 HTML 대신 로그인 페이지 반환
- `/api/admin/login` 성공 시 보안 쿠키 세션 발급
- `/api/admin/session`으로 현재 인증 상태 확인
- `/api/admin/logout`으로 세션 종료
- 기존 헤더 토큰 방식은 보조 호환 경로로 유지

### 관리자 UI/UX
- 관리자 첫 화면 문구를 서버 인증 기준으로 수정
- “토큰 지우기”를 실제 로그아웃 동작으로 변경
- 클라이언트에 관리자 비밀키를 저장하지 않도록 변경
- 관리자 설정 폼에 자동발행 주기/빈도/시간대/대상 제품/모드 추가

### 자동발행
- 설정 저장 시 DB에 자동발행 설정 반영
- 스케줄러는 설정된 주기/빈도/시간대 기준으로 발행 가능한 건수를 계산
- 선택 제품 또는 전체 제품을 round-robin으로 자동 발행
- 즉시 발행 버튼은 수동 1회 발행 유지

## 6. 확인 결과
### 로컬 스모크 체크
- 비인증 `/admin/index.html` → 로그인 HTML 반환 확인
- `/api/admin/session` → `authenticated: false` 확인
- `/api/admin/login` → 세션 쿠키 발급 확인
- 인증 후 `/api/admin/state` 접근 성공 확인
- `/api/admin/board-settings` 저장 시 `scheduleType`, `frequencyPerRun`, `timeSlots`, `selectedProducts` 반영 확인

## 7. 남은 주의사항
- `admin_state` 응답이 매우 커서 운영상 필요 시 대시보드용 경량 endpoint 분리가 바람직함
- `publishMode=draft`는 현재 저장되지만 공개 자료실 모델이 단일 publication 구조라 별도 초안 분기 UI까지는 아직 구현되지 않음
- 운영 배포 시 `NV0_ADMIN_TOKEN`, `NV0_BACKUP_PASSPHRASE`는 충분히 긴 실제 비밀값으로 교체 필요

## 8. 배포 메모
- 변경본 배포 후 브라우저 캐시 때문에 기존 JS가 남아 있을 수 있으므로 강력 새로고침 권장
- 기존 세션스토리지의 관리자 토큰 값은 사용되지 않음
