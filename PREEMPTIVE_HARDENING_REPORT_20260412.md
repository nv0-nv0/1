# NV0 선제 보완 완료 보고서 (2026-04-12)

## 이번에 선제 조치한 항목
- 이메일 입력값을 소문자로 정규화해 주문/포털 조회 불일치 방지
- 조회 코드를 대문자로 정규화해 복붙/대소문자 차이로 인한 조회 실패 방지
- 코드 생성 suffix 길이 확장으로 동시 생성 충돌 가능성 추가 축소
- DB 경로 parent 자동 생성으로 커스텀 `NV0_DB_PATH` 환경에서 초기 기동 실패 방지
- `x-forwarded-host`, `x-forwarded-proto` 반영으로 프록시/쿨리파이 뒤 canonical redirect 오판 가능성 축소
- full 모드 실결제에서 Toss 키 누락 시 reserve 단계에서 즉시 차단하고 명확한 오류 반환
- 운영 full 모드 + 실결제 + 비로컬 환경에서 Toss 키 누락 시 startup fail-fast 적용
- webhook fingerprint 중복 감지로 재전송/중복 webhook 재처리 최소화
- backup 디렉터리 writable 상태를 admin health verbose에 노출
- 프론트 폼 더블클릭 방지 submit lock 추가
- 결제 스크립트 미로드/결제 설정 미완료 상태에서 오해 소지가 있는 안내 대신 명확한 오류 표시
- 포털 조회 시 원격 응답의 order/publications를 우선 반영해 상태 동기화 지연으로 인한 조회 실패 보완
- `.env.example`를 최신 preflight 규칙과 일치하도록 조정

## 추가 검증 항목
- portal lookup 대소문자 정규화 검증 추가
- duplicate webhook ignored 검증 추가
- 기존 confirm/webhook 경합, publication dedup, packaging/runtime 검증 재통과

## 최종 상태
- full 모드: 즉시 시연 / 결제 진입 / 결제 후 자동 발행 / 포털 확인 흐름 유지
- board-only 모드: 기존 범위와 차단 정책 유지
- 남은 외부 확인: Toss 실키로 소액 1회 실결제 및 실제 webhook 수신 최종 점검
