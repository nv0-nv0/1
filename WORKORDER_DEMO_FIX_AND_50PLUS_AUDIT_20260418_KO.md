# NV0 / Veridion 데모 긴급 안정화 + 50개 이상 중분류 작업지시서

## 1. 작업 모드
- 판정: 긴급 안정화 모드
- 최우선 장애: 무료 데모가 정상 체감 동작하지 않음
- 핵심 원인: 공개 API가 데모 응답마다 전체 운영 상태를 함께 내려 브라우저 파싱 부담과 공개 데이터 노출을 동시에 유발함

## 2. 실제 확인 완료 핵심 사실
1. 수정 전 `/api/public/veridion/scan` 응답 크기는 **14,637,909 bytes**였음.
2. 수정 전 공개 응답 본문에 `accounts`, `sessions`, `passwordHash`, `token` 계열 데이터가 포함됐음.
3. 공개 데모/문의/조회/주문 관련 API 다수가 `state_payload()`를 그대로 반환하고 있었음.
4. `state_payload()`는 `orders`, `demos`, `contacts`, `lookups`, `reports`, `publications`, `webhook_events`, `scheduler`, `assets`, `accounts`, `sessions`를 모두 포함함.
5. 수정 후 `/api/public/veridion/scan` 응답 크기는 **15,158 bytes**로 감소함.
6. 수정 후 `/api/public/demo-requests` 응답 크기는 **8,218 bytes**였음.
7. 수정 후 공개 응답에서 `accounts`, `sessions`, `passwordHash` 문자열이 검출되지 않았음.
8. 수정 후 `scripts/public_payload_regression.py` 회귀 검증 통과.
9. 수정 후 `scripts/veridion_runtime_regression.py`가 데모→결제→인테이크→포털 흐름까지 통과.
10. 라이브 공개 화면에는 현재도 `관리` 링크가 노출됨. citeturn2view0turn2view2
11. 홈은 Veridion 한 제품 집중을 강조하지만, 가이드 페이지에는 ClearPort/GrantOps/DraftForge 즉시 데모 링크가 함께 노출됨. citeturn2view0turn2view1
12. 공개 자료실 글 보기 페이지는 실제 글 본문보다 허브 안내 위주 구조로 보임. citeturn2view2

## 3. 이번 턴 실제 반영 내용
### 반영 파일
- `server_app.py`
- `scripts/public_payload_regression.py`
- `WORKORDER_DEMO_FIX_AND_50PLUS_AUDIT_20260418_KO.md`

### 실제 수정
1. 공개 API 응답에서 전체 `state_payload()` 반환 제거.
2. 데모 스캔/분석/문의/포털/주문 관련 공개 응답을 최소 payload 구조로 축소.
3. 공개 payload 크기·민감 문자열 누출 여부를 검증하는 회귀 스크립트 추가.
4. 데모→결제→포털 흐름 회귀 테스트 재실행.

## 4. 문제점 58개 중분류 목록
상태는 아래 4개로만 기록함.
- 실제 확인 완료
- 동작 확인 필요
- 검증 미완료
- 확인되지 않음

| ID | 대분류 | 중분류 | 상태 | 우선순위 | 판단 근거 | 조치 방향 |
|---:|---|---|---|---|---|---|
| 1 | 데모/API | 공개 데모 응답 과대 payload | 실제 확인 완료 | P0 | 수정 전 scan 14.6MB | 공개 응답 최소화 유지 |
| 2 | 데모/API | 공개 응답에 전체 state 포함 | 실제 확인 완료 | P0 | `state_payload()` 직접 반환 | 공개/관리 응답 경계 분리 |
| 3 | 보안 | 공개 응답에 accounts 노출 | 실제 확인 완료 | P0 | 응답 본문 문자열 검출 | 공개 응답 차단 유지 |
| 4 | 보안 | 공개 응답에 sessions 노출 | 실제 확인 완료 | P0 | 응답 본문 문자열 검출 | 공개 응답 차단 유지 |
| 5 | 보안 | 공개 응답에 passwordHash 노출 | 실제 확인 완료 | P0 | 응답 본문 문자열 검출 | 공개 응답 차단 유지 |
| 6 | 보안 | 공개 응답에 token 계열 노출 가능성 | 실제 확인 완료 | P0 | 수정 전 state 구조상 포함 | 공개 응답 차단 유지 |
| 7 | 성능 | 브라우저 JSON 파싱 부담 과다 | 실제 확인 완료 | P0 | 14.6MB JSON | 응답 최소화 + 회귀 테스트 |
| 8 | 성능 | 네트워크 낭비 | 실제 확인 완료 | P0 | 데모 1회당 과대 응답 | 공개 API slim 응답 유지 |
| 9 | UX | 무료 데모 체감 지연 | 실제 확인 완료 | P0 | 과대 payload가 직접 원인 | 응답 축소로 개선 |
| 10 | 데모/API | demo-requests에 불필요 state 반환 | 실제 확인 완료 | P0 | 코드 검토 | 제거 완료 |
| 11 | 데모/API | contact-requests에 불필요 state 반환 | 실제 확인 완료 | P0 | 코드 검토 | 제거 완료 |
| 12 | 데모/API | portal-lookup에 불필요 state 반환 | 실제 확인 완료 | P0 | 코드 검토 | 제거 완료 |
| 13 | 데모/API | orders/reserve에 불필요 state 반환 | 실제 확인 완료 | P0 | 코드 검토 | 제거 완료 |
| 14 | 데모/API | payments/confirm에 불필요 state 반환 | 실제 확인 완료 | P0 | 코드 검토 | 제거 완료 |
| 15 | 데모/API | orders/{id}/intake에 불필요 state 반환 | 실제 확인 완료 | P0 | 코드 검토 | 제거 완료 |
| 16 | 아키텍처 | 공개/관리 응답 경계 미분리 | 실제 확인 완료 | P1 | 공용 `state_payload()` 재사용 | public/admin serializer 분리 |
| 17 | QA | 공개 payload 크기 회귀 테스트 부재 | 실제 확인 완료 | P1 | 기존 테스트 없음 | 스크립트 추가 완료 |
| 18 | QA | 민감 문자열 누출 회귀 테스트 부재 | 실제 확인 완료 | P1 | 기존 테스트 없음 | 스크립트 추가 완료 |
| 19 | QA | 브라우저 레벨 체감 검증 자동화 부재 | 동작 확인 필요 | P1 | 서버 회귀만 존재 | Playwright급 E2E 추가 |
| 20 | 보안 | `/api/admin/state`의 raw state 노출 범위 과다 | 실제 확인 완료 | P1 | admin state가 전체 records 반환 | 관리자 응답도 민감 필드 마스킹 |
| 21 | 보안 | 관리자 state의 session token 평문 전달 | 실제 확인 완료 | P1 | state 구조상 세션 token 포함 | token 마스킹/미반환 |
| 22 | 보안 | 관리자 state의 passwordHash 전달 | 실제 확인 완료 | P1 | state 구조상 hash 포함 | hash 미반환 |
| 23 | 아키텍처 | `server_app.py` 단일 대형 파일 구조 | 실제 확인 완료 | P1 | 단일 파일 수천 라인 | public/admin/report 모듈 분리 |
| 24 | 운영 | STORE_TYPES에 accounts/sessions 포함된 단일 state 모델 | 실제 확인 완료 | P1 | 코드 검토 | 공개/관리/보안 스토어 분리 |
| 25 | 운영 | 캐시 단위가 state 전체 기준 | 실제 확인 완료 | P2 | `_STATE_CACHE` 전체 캐시 | record-type별 응답 캐시 분리 |
| 26 | 성능 | scan 응답에 preview/report 동시 포함 | 실제 확인 완료 | P2 | 응답 구조 확인 | 필요 시 preview 경량화 |
| 27 | 데모/API | example.com 외부 스캔 실패 시 fallback 설명이 길고 복잡함 | 실제 확인 완료 | P2 | 스캔 결과 확인 | 실패 메시지 1차 요약 축소 |
| 28 | 보안 | 공개 화면에 관리 링크 노출 | 실제 확인 완료 | P1 | 라이브 홈/글보기 페이지 상단 노출 citeturn2view0turn2view2 | 공개 네비에서 숨기고 별도 관리자 진입 사용 |
| 29 | IA | 홈은 단일 제품 집중 메시지이나 다른 모듈 진입이 함께 노출 | 실제 확인 완료 | P2 | 홈/가이드 내용 비교 citeturn2view0turn2view1 | 공개 메시지/링크 구조 정리 |
| 30 | IA | 가이드 페이지에서 보조 모듈 즉시 데모 노출 | 실제 확인 완료 | P2 | 가이드 라인 15~29 citeturn2view1 | Veridion 중심 단계형 공개로 재정렬 |
| 31 | IA | 자료실 글 보기 페이지의 실제 글 소비 흐름 약함 | 실제 확인 완료 | P2 | 허브 안내 중심 구조 citeturn2view2 | 글 본문 우선 구조로 전환 |
| 32 | 카피 | 홈 핵심 흐름 문장이 한 줄에 과밀 | 실제 확인 완료 | P2 | 홈 34행 문장 밀집 citeturn2view0 | 단계 카드형으로 분해 |
| 33 | 카피 | 무료/유료 경계 설명 문장량 과다 | 실제 확인 완료 | P2 | 홈 16~29행 반복성 높음 citeturn2view0 | 무료/유료 비교표 1개로 압축 |
| 34 | 전환 | 첫 화면 CTA가 3개 병렬이라 초점 분산 | 실제 확인 완료 | P2 | 홈 14행 CTA 3개 citeturn2view0 | 1차 CTA 1개 + 보조 1개로 축소 |
| 35 | 전환 | 관리 링크가 공개 신뢰 동선을 방해 | 실제 확인 완료 | P1 | 라이브 상단 노출 citeturn2view0turn2view2 | 공개 헤더 제거 |
| 36 | 콘텐츠 | “한 제품 집중” 메시지와 “분리 모듈 허브” 메시지 동시 노출 | 실제 확인 완료 | P2 | 홈 30~33, 68~75행 citeturn2view0 | 공개 단계에 따라 노출 분리 |
| 37 | SEO/콘텐츠 | 자료실 글 상세 페이지 요약성 과다 | 실제 확인 완료 | P2 | 글 보기 본문 얕음 citeturn2view2 | 본문 depth 보강 |
| 38 | SEO/콘텐츠 | 제품/가이드/자료실 간 문장 반복도 높음 | 동작 확인 필요 | P2 | 공개 텍스트 유사 구조 | 카피 중복도 점검 스크립트 추가 |
| 39 | 접근성 | 공개 관리 링크가 키보드 포커스 순서에 개입 | 동작 확인 필요 | P2 | 관리 링크 상단 고정 | focus order 수동 QA |
| 40 | 접근성 | 데모 결과 영역 live-region 여부 | 동작 확인 필요 | P2 | DOM 수동 확인 미실시 | aria-live 점검 |
| 41 | 접근성 | 폼 오류 시 스크린리더 메시지 충분성 | 동작 확인 필요 | P2 | 서버 검증만 확인 | aria-describedby 정비 |
| 42 | 성능 | 외부 사이트 스캔 timeout 체감 | 실제 확인 완료 | P2 | example.com 결과에서 실시간 fetch 제한 메시지 확인 | timeout/실패 UX 개선 |
| 43 | 성능 | fallback 결과 생성 시 불필요한 상세 데이터 구성 | 동작 확인 필요 | P3 | report/preview 중복 존재 | 경량 preview 템플릿 검토 |
| 44 | 보안 | 공개 포털 조회 응답 최소화 여부 | 실제 확인 완료 | P1 | state 제거 완료 | order/publications 외 최소 필드 검토 |
| 45 | 보안 | 문의/데모 저장 후 공개 응답에 내부 메타 과다 가능성 | 동작 확인 필요 | P2 | 현재는 state 제거만 수행 | response schema 고정 |
| 46 | 운영 | 회귀 검증이 scripts 수동 실행 중심 | 실제 확인 완료 | P2 | CI 구성 미확인 | 배포 파이프라인에 자동 연결 |
| 47 | 운영 | 배포 전 quality gate 자동 실패 기준 부족 | 동작 확인 필요 | P2 | 스크립트는 있으나 CI 연결 미확인 | Coolify pre-deploy hook 연결 |
| 48 | QA | 브라우저 렌더 성능 기준값 부재 | 검증 미완료 | P2 | LCP/TTI 기준 없음 | 기준 수립 |
| 49 | QA | 모바일 실기기 데모 체감 검증 미실시 | 검증 미완료 | P1 | 서버 검증만 수행 | 390px/430px 실제 브라우저 QA |
| 50 | QA | Safari 계열 데모 동작 검증 미실시 | 검증 미완료 | P2 | 컨테이너 한계 | 후속 브라우저 매트릭스 |
| 51 | QA | Edge/Chrome 공개 데모 클릭 스모크 자동화 부재 | 동작 확인 필요 | P1 | 서버 레벨만 검증 | Playwright 스모크 추가 |
| 52 | 운영 | 민감 필드 마스킹 표준 부재 | 실제 확인 완료 | P1 | 응답 계층 분리만 적용 | serializer 정책 문서화 |
| 53 | 문서 | 공개/관리 응답 정책 문서 부재 | 실제 확인 완료 | P2 | 별도 명세 없음 | API boundary 문서 추가 |
| 54 | 문서 | 데모 정상 판정 기준 문서 부재 | 실제 확인 완료 | P2 | 수치 기준 미정 | 정상 판정표 작성 |
| 55 | 안정성 | 공개 스캔 실패 시 원인 분류가 거칠음 | 실제 확인 완료 | P2 | 봇 차단/TLS/지역 제한 묶음 처리 | 실패 원인 코드 세분화 |
| 56 | 안정성 | robots/sitemap 부재와 실제 fetch 실패가 같은 체감 오류로 보임 | 실제 확인 완료 | P2 | 예시 스캔 결과 확인 | 진단 분리 표시 |
| 57 | 제품 | 무료 데모 가치와 유료 발행 가치 경계는 명확하나 정보량 밸런스 추가 조정 필요 | 실제 확인 완료 | P3 | 라이브 공개 카피 검토 citeturn2view0turn2view1 | 요약형 비교표 정리 |
| 58 | 운영/보안 | 관리자 접근 방식이 공개 네비 링크 의존 흔적 남음 | 실제 확인 완료 | P1 | 공개 `관리` 노출 + admin API 존재 citeturn2view0turn2view2 | 별도 비공개 진입 경로로 분리 |

## 5. 작업 지시서
### 작업 1. 공개 payload 경계 고정
- 우선순위: P0
- 목적: 데모 체감 지연 제거 + 공개 데이터 누출 차단
- 원인: 공개 응답에 `state_payload()` 직결
- 상세 조치:
  - 공개 엔드포인트에서 `state_payload()` 반환 금지
  - 공개 응답은 `order/demo/contact/report/preview` 등 필요한 필드만 유지
  - `accounts/sessions/passwordHash/token` 문자열 회귀 차단
- 대상 파일/영역: `server_app.py`
- 완료 조건: scan/demo 응답에서 state 부재, 민감 필드 미검출
- 롤백 조건: 프론트 공개 흐름에서 필수 데이터 누락 발생 시

### 작업 2. 공개 payload 회귀 자동화
- 우선순위: P0
- 목적: 동일 장애 재발 방지
- 원인: payload 크기·민감 필드 회귀 검증 부재
- 상세 조치:
  - `scripts/public_payload_regression.py` 추가
  - scan/demo 응답 크기 상한선 검증
  - 민감 문자열 미포함 검증
- 완료 조건: 스크립트 통과
- 롤백 조건: 없음

### 작업 3. Veridion 핵심 흐름 재검증
- 우선순위: P0
- 목적: 데모 수정이 주문/포털 흐름을 깨지 않았는지 확인
- 상세 조치:
  - 데모→reserve→confirm→intake→portal lookup 회귀 실행
- 대상 파일/영역: `scripts/veridion_runtime_regression.py`
- 완료 조건: 전체 흐름 통과

### 작업 4. 관리자 응답 민감 필드 마스킹
- 우선순위: P1
- 목적: 관리자 화면이더라도 불필요한 비밀값 재배포 차단
- 상태: 동작 확인 필요
- 상세 조치:
  - admin state에서 `passwordHash`, `token` 제외 또는 마스킹
  - 세션 조회는 count/metadata 중심으로 축소

### 작업 5. 공개 헤더에서 관리자 진입 제거
- 우선순위: P1
- 목적: 공개 전환 흐름 방해 제거
- 상태: 동작 확인 필요
- 상세 조치:
  - 공개 화면 상단 `관리` 링크 숨김
  - 비공개 관리자 진입 URL/단축 경로 별도 운용

### 작업 6. 공개 메시지 구조 정리
- 우선순위: P2
- 목적: Veridion 단일 제품 집중 메시지와 모듈 허브 메시지 충돌 제거
- 상태: 동작 확인 필요
- 상세 조치:
  - 홈은 Veridion만 판매/데모 중심으로 유지
  - 가이드/자료실의 보조 제품 노출은 운영자용 또는 후순위 섹션으로 이관

## 6. 하네스 설계
### L2 반자동 하네스
1. `python3 scripts/public_payload_regression.py --base-url http://127.0.0.1:{port}`
2. `python3 scripts/veridion_runtime_regression.py --base-url http://127.0.0.1:{port}`
3. 브라우저 수동 검증:
   - 홈 → 무료 데모 클릭
   - URL 입력 후 결과 3초 내 1차 렌더 체감 확인
   - 결과 카드/CTA/결제 진입 확인
   - 포털 조회 확인

### 기대 결과
- 공개 데모 응답에 state 없음
- 민감 필드 없음
- 무료 데모 결과 렌더 가능
- 결제 이후 인테이크/포털 흐름 정상

### 실패 조건
- 응답에 `accounts/sessions/passwordHash/token` 검출
- scan 응답 과대화
- 데모 결과 미렌더
- 결제 후 포털 조회 실패

## 7. 실제 테스트 결과
### 수행한 테스트
1. `python3 -m py_compile server_app.py`
2. `python3 -m py_compile scripts/public_payload_regression.py`
3. 로컬 uvicorn 기동 후 `/health` 확인
4. 공개 payload 회귀 테스트 실행
5. Veridion runtime regression 실행

### 결과
- `server_app.py` 구문 검증: 통과
- `public_payload_regression.py`: 통과
  - scan payload: 15,158 bytes
  - demo-request payload: 8,218 bytes
  - state 미포함
  - 민감 문자열 미검출
- `veridion_runtime_regression.py`: 통과
  - reportCode 발급 정상
  - riskScore 계산 정상
  - deliveryRuleCount 5
  - deliveryPageActionCount 8
  - deliveryRemediationCount 5
  - portal lookup 정상

## 8. 남은 리스크
1. 공개 헤더 `관리` 링크는 아직 라이브에서 보임. citeturn2view0turn2view2
2. admin state 민감 필드 마스킹은 이번 턴 미반영.
3. 실제 브라우저 렌더링 체감은 서버/API 기준으로만 확인했고, 실브라우저 클릭 자동화는 미구축.
4. 라이브 사이트 배포 검증은 이번 로컬 패키지 기준이며, 실제 배포본 반영 여부는 별도 확인 필요.

## 9. 최종 판정
- 즉시 검토 가능 여부: 가능
- 즉시 시연 가능 여부: 로컬 패키지 기준 가능
- 즉시 인수 검토 가능 여부: 가능
- 즉시 납품 가능 여부: **조건부 가능**
- 즉시 운영 가능 여부: **조건부 가능**
- 즉시 장애 대응 가능 여부: 가능
- 추가 조치 필요 여부: 필요

### 조건부 사유
- 데모 핵심 장애 원인은 제거했고 회귀 테스트도 통과했음.
- 다만 공개 헤더의 관리자 노출과 admin state 민감 필드 마스킹은 후속 보완이 필요함.
