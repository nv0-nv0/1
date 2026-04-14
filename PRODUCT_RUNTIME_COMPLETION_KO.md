# NV0 제품 런타임 완성 설계 및 검증 요약

## 1. 이번 보강 목표
이번 보강의 목표는 4개 제품이 모두 아래 흐름을 실제로 통과하도록 만드는 것이었습니다.

1. 제품별 즉시 데모가 바로 작동할 것
2. 결제 예약과 결제 확정 이후 제품 결과물이 자동으로 생성될 것
3. 고객 포털에서 같은 조회 코드로 결과물과 발행 글을 확인할 수 있을 것
4. 결과물이 단순 제목 나열이 아니라, 고객이 돈을 낼 이유를 느낄 만큼 구체적일 것

## 2. 제품별 공통 런타임 구조
모든 제품은 아래 공통 런타임을 사용합니다.

- 데모 요청 저장
- 제품별 샘플 결과 미리보기 생성
- 결제 예약 생성
- Toss mock 또는 live confirm 이후 자동 납품 처리
- 결과 패키지 생성
- 자동 발행 글 2건 이상 생성
- 고객 포털 조회
- 관리자 상태 확인 및 재발행

## 3. 이번에 강화한 핵심
### 3-1. 데모 미리보기 강화
기존에는 제품 출력 항목 제목 위주로 보이던 데모 결과를, 아래 구조로 강화했습니다.

- 제품별 샘플 결과 headline
- 샘플 결과 요약
- 샘플 결과물 3개 이상
- 바로 체감할 가치 항목
- 확인 기준 항목
- 결제로 이어지는 CTA 힌트

### 3-2. 결제 후 결과 패키지 강화
기존 resultPack은 제목과 간단한 note 수준이었으나, 지금은 아래를 포함합니다.

- outcomeHeadline
- clientContext
- outputs 전체
- output별 preview/whyItMatters/deliveryState
- quickWins
- valueDrivers
- successMetrics
- issuanceBundle
- deliveryAssets
- nextActions
- valueNarrative

### 3-3. 고객 포털 강화
고객 포털에서 아래를 바로 볼 수 있게 했습니다.

- 제품 / 플랜 / 결제 상태 / 결과 상태
- 결과 전달 요약
- 출력물별 preview
- 발행 준비 상태
- 이 결과가 바로 도움이 되는 이유
- 연결된 공개 글 목록

## 4. 제품별 완성 기준
### Veridion
- 데모: 법률 준수 점검 샘플 결과, 과태료 미리보기, 우선순위 제시
- 결제 후: 준수 스캔 리포트, 수정안, 변경 감시 큐, 발행 글 생성

### ClearPort
- 데모: 준비 서류 기준표, 보완 요청 템플릿, 단계별 고객 안내 미리보기
- 결제 후: 기준표, 템플릿 세트, 운영 체크리스트, 발행 글 생성

### GrantOps
- 데모: 공고 해석, 제출 체크리스트, 일정표·역할 분담 미리보기
- 결제 후: 제출 구조 자료, 보완 대응 메모, 재사용 운영본, 발행 글 생성

### DraftForge
- 데모: 검토 흐름, 승인 체크리스트, 최종본 비교표 미리보기
- 결제 후: 승인 체계, 버전 규칙, QA 체크리스트, 발행 글 생성

## 5. 자동 검증 항목
이번에는 단일 제품 smoke가 아니라 4개 제품 전부에 대해 아래를 자동 검증하도록 스크립트를 추가했습니다.

- 제품 페이지 접근
- 제품 데모 페이지 접근
- 데모 요청 생성
- preview sampleOutputs 최소 길이 검증
- preview quickWins/valueDrivers 검증
- 결제 예약
- mock 결제 확정
- delivered 상태 확인
- resultPack outputs/quickWins/valueDrivers/successMetrics/issuanceBundle 길이 검증
- publicationIds 생성 검증
- 고객 포털 lookup 검증

검증 스크립트: `scripts/product_runtime_e2e.py`

## 6. 패키지 완성 게이트 반영
패키지 완성 게이트에 아래 항목을 추가했습니다.

- full mode build
- full mode preflight
- full mode smoke
- full mode post deploy verify
- full mode all-product runtime e2e
- full mode audit
- board-only build
- board-only preflight
- board-only smoke
- board-only audit
- 최종 full 복원

## 7. 아직 외부 환경에서 확인되지 않은 항목
다음 3개는 패키지 내부가 아니라 운영 환경 검증이 필요합니다.

- 실제 nv0.kr 반영
- Toss 실결제
- Veridion 법령 API live 연결

이 3개를 제외한 패키지 내부 런타임 기준으로는, 4개 제품의 데모·결제·결과물·발행 흐름이 모두 확인되었습니다.
