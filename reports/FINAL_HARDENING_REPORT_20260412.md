# NV0 최종 보완 보고서 (2026-04-12)

## 최종 판정
실행형 데모, 외부 결제 진입, 결제 후 자동 발행, 포털 조회 흐름은 유지한 상태로 추가 보완을 완료했습니다.

현재 상태:
- 전체 빌드 통과
- 전체 테스트 통과
- 강건성(중복 결제/동시 승인/웹훅 경합/코드 중복) 테스트 통과
- board-only 회귀 테스트 통과
- 패키징/런타임 테스트 통과

## 이번에 실제로 보완한 항목

### 1) 사용자-facing 코드 중복 방지
기존에는 주문/데모/문의 코드가 `건수 + 1` 기반이라 동시 요청 시 중복 가능성이 있었습니다.

수정:
- `server_app.py`
  - `make_public_code()` 추가
  - 주문/데모/문의 코드 생성 방식을 `제품 prefix + UTC timestamp + random suffix`로 변경
- `src/assets/site.js`
  - 로컬/폴백 모드에서도 같은 방식의 `makePublicCode()` 적용

효과:
- 동시에 여러 요청이 들어와도 코드 충돌 위험 대폭 감소

### 2) 결제 승인 중복 처리 방어
기존에는 같은 주문에 대해 결제 성공 페이지 재호출, 중복 클릭, confirm/webhook 경합 시 중복 발행 가능성이 있었습니다.

수정:
- `server_app.py`
  - `order_lock()` 추가
  - `confirm_toss_payment()`에 주문 단위 락 적용
  - 이미 결제 완료된 주문은 같은 paymentKey면 idempotent 반환
  - 다른 paymentKey로 재승인 시 409 충돌 처리

효과:
- 성공 페이지 새로고침/재호출 시 이중 발행 방지
- 잘못된 다른 결제키 재확인 차단

### 3) confirm ↔ webhook 경합 시 중복 발행 방어
기존에는 confirm과 webhook이 거의 동시에 들어오면 publication이 중복 생성될 여지가 있었습니다.

수정:
- `server_app.py`
  - `handle_toss_webhook()`에도 주문 단위 락 적용
  - `ensure_publications_for_order()`가 `publicationIds`뿐 아니라 `orderId`, `code prefix` 기준으로도 기존 발행물을 재탐색하도록 보강

효과:
- confirm/webhook 경합에서도 같은 주문의 발행 카드가 중복 생성되지 않음

### 4) 예약 주문 재생성 방어
기존에는 같은 order id로 reserve가 반복되면 다시 덮어쓸 수 있었습니다.

수정:
- `reserve_toss_order()`에 주문 단위 락과 기존 상태 재사용 로직 추가

효과:
- 반복 reserve 요청에도 기존 준비 주문 재사용 가능

### 5) 포털 조회 내구성 보강
기존 프론트는 포털 조회 후 서버가 내려준 order/publications보다 로컬 상태에 더 의존하는 구간이 있었습니다.

수정:
- `src/assets/site.js`
  - `bindPortalLookup()`에서 remote 응답의 `order`, `publications`를 우선 사용
  - `resultPack` 누락 시 안전한 fallback 추가

효과:
- 관리자 토큰 없이도 공개 포털 조회 결과가 더 안정적으로 렌더링됨
- 로컬 캐시와 원격 상태가 살짝 어긋나도 표시 안정성 향상

## 추가한 검증
새 테스트 파일:
- `tests/robustness_check.py`

검증 내용:
1. 주문/데모/문의 코드 10회 연속 생성 시 모두 유일한지 확인
2. 같은 주문 confirm 5회 동시 호출 시 publication이 정확히 2개만 생성되는지 확인
3. confirm과 webhook를 동시에 호출해도 publication이 정확히 2개만 유지되는지 확인

결과:
- `ROBUSTNESS_OK`

## 전체 재검증 결과
- `python3 tests/test_all.py` 통과
- `python3 tests/packaging_runtime_check.py` 통과
- `python3 tests/robustness_check.py` 통과

## 최종 산출물
- 최종 프로젝트 ZIP: `nv0proj_hardened_20260412.zip`
- 본 보고서: `FINAL_HARDENING_REPORT_20260412.md`
