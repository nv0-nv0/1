# A. 작업 목표 재정의
- 최종 목표: nv0.kr를 내부 운영형 설명 사이트가 아니라 제품을 이해하고 바로 구매 판단할 수 있는 판매 페이지 기준으로 재정렬
- 기대 인수 기준: 첫 화면에서 무엇을 파는지, 누구에게 맞는지, 무엇을 받는지, 왜 지금 사야 하는지가 바로 이해될 것
- 범위: 공개 고객 화면 카피, 제품 설명, CTA, 가격/데모/문의/포털 문구, 전역 네비게이션/푸터, 검증 스크립트 1건
- 비범위: 실서버 배포 반영, 외부 결제사 실결제 1회, 운영 도메인 실제 DNS/SSL 제어
- 완료 기준: 카피가 판매형 기준으로 재작성되고, 로컬 전체 검증 게이트가 통과할 것
- 납품 판단 기준: full/board 검증 스크립트가 통과하고, 고객용 공개 문구에서 내부 운영형 표현이 크게 줄어들 것

# B. 현재 상태 및 자료 범위
- 제공 자료: nv0_delivery_package_fixed_full_20260414_v2.zip, 붙여넣은 텍스트 (1).txt
- 자동 수집 자료: build.py, scripts/generate_compat_pages.py, src/assets/site.js, src/data/site.json, server_app.py, 검증 스크립트 세트
- 확인 가능한 범위: 프로젝트 소스, 정적 페이지 산출물, 로컬 실행, 로컬 API/스모크/E2E, 공개 도메인 텍스트 스냅샷
- 확인되지 않은 범위: 운영 서버 실제 파일 반영 상태, Coolify 실제 컨테이너 교체 여부, Toss 실결제 live, 운영 도메인 프록시/SSL 실상태
- 작동 모드: 실행 모드
- 핵심 사용자 시나리오:
  1) 홈 진입 → 제품 선택
  2) 제품 이해 → 샘플 결과 확인
  3) 가격/플랜 검토 → 결제
  4) 결제 후 포털 확인
  5) 예외 조건 문의

# C. 정밀 사전 진단
## 1) 판매 페이지 관점 부재
- 증상: 설명 중심, 구조 설명 중심, 내부 운영 뉘앙스가 강함
- 실제 문제 후보: 고객이 "무엇을 사는지"보다 "어떻게 설계했는지"를 먼저 읽게 됨
- 구조적 원인 후보: 브랜드/제품/네비게이션/헬퍼 문구가 엔진/운영/흐름 중심으로 작성됨
- 영향 범위: 홈, 제품 목록, 제품 상세, 문서/가이드/가격/게시판 허브
- 우선순위: 높음
- 방치 시 리스크: 이해 지연, 호감 저하, 전환 저하

## 2) 전역 카피 톤 불일치
- 증상: 버튼/네비게이션/헬퍼 문구가 내부 용어와 고객 용어가 섞여 있음
- 실제 문제 후보: CTA가 약하고 다음 행동이 덜 명확함
- 구조적 원인 후보: build.py, generate_compat_pages.py, site.js, site.json이 각각 다른 톤으로 작성됨
- 영향 범위: 전 페이지 공통
- 우선순위: 높음
- 방치 시 리스크: 고객 행동 유도 실패, 페이지 신뢰감 저하

## 3) 제품 설명 부족
- 증상: 제품 가치 설명이 기능/흐름 중심이고 구매 이유 설명이 약함
- 실제 문제 후보: 고객이 "그래서 내게 어떤 이득이 생기나"를 바로 이해하지 못함
- 구조적 원인 후보: product headline/summary/value_points/output/faq가 판매형 메시지로 최적화되지 않음
- 영향 범위: Veridion / ClearPort / GrantOps / DraftForge 전체
- 우선순위: 높음
- 방치 시 리스크: 제품별 차별성 약화

## 4) 검증 게이트 취약점
- 증상: package_completion_gate가 포트 충돌 상황에서 잘못된 인스턴스를 물 가능성 존재
- 실제 문제 후보: 검증 스크립트 신뢰도 저하
- 구조적 원인 후보: 고정 포트 8010/8011 사용
- 영향 범위: 로컬 검증 자동화
- 우선순위: 중간
- 방치 시 리스크: 검증 결과 오판

# D. 정밀 설계
- 해결 원칙:
  1) 내부 운영 설명보다 고객 구매 판단을 앞세운다.
  2) 문제 → 기대 결과 → 증거/샘플 → 가격/다음 행동 순으로 정리한다.
  3) 같은 의미의 문구라도 고객 언어로 통일한다.
  4) 기능 삭제보다 카피/동선 교정 중심으로 반영한다.
- 수정 범위: 4개 핵심 소스 파일 + 1개 검증 스크립트
- 영향 범위: 공개 고객 화면 전체, 제품 상세 전반, 전체 빌드 산출물, 로컬 검증 게이트
- 회귀 위험: 낮음~중간. 기능 로직보다는 카피와 테스트 유틸 수정 중심
- 검증 방식: py_compile, node --check, build, package_completion_gate, smoke_release, post_deploy_verify, product_runtime_e2e, result_quality_gate, api_safety_regression, board_mode_regression
- 완료 판정 기준: 전체 로컬 검증 통과 + 공개 페이지 카피 재작성 완료
- 안전한 변경 순서:
  1) site.json 제품/브랜드 카피 개편
  2) build.py 공개 페이지 핵심 카피 개편
  3) generate_compat_pages.py 보조 페이지 카피 개편
  4) site.js 전역 nav/footer/CTA 보정
  5) package_completion_gate 포트 충돌 보완
  6) 전체 rebuild 및 전역 검증

# E. 작업 지시서
## 작업 1. 브랜드/홈 전환 카피 개편
- 우선순위: 높음
- 목적: 첫 화면에서 무엇을 파는지와 왜 필요한지를 바로 이해시키기
- 원인: 구조 설명 위주 문구 과다
- 상세 조치: hero/tagline/company_profile/trust_points 재작성, 홈 CTA 교체
- 대상 파일/영역: src/data/site.json, build.py
- 선행 조건: 기존 기능 보존
- 영향 범위: 홈, 회사, 제품 목록
- 검증 항목: 빌드 성공, 홈 노출 카피 확인
- 완료 조건: 홈 첫 화면 판매형 카피 반영

## 작업 2. 제품 4종 판매형 설명 재작성
- 우선순위: 높음
- 목적: 제품 차이와 구매 이유를 더 직관적으로 보여주기
- 원인: 기능/흐름 위주 설명
- 상세 조치: headline, summary, problem, value_points, outputs, fit_for, workflow, FAQ, plan note 재작성
- 대상 파일/영역: src/data/site.json
- 영향 범위: 제품 카드, 제품 상세, 가격/문서/가이드/FAQ 보조 페이지
- 검증 항목: 제품 상세/플랜/문서/FAQ 노출 문구 확인
- 완료 조건: 4개 제품 모두 구매 이유 중심으로 재작성

## 작업 3. 전역 CTA/네비게이션 정리
- 우선순위: 높음
- 목적: 고객 행동 유도를 더 명확하게 만들기
- 원인: 내부 용어·추상 용어 섞임
- 상세 조치: nav label, footer label, CTA 문구, 상태/도움말 문구 수정
- 대상 파일/영역: src/assets/site.js
- 영향 범위: 전 페이지 공통 헤더/푸터/동적 카드
- 검증 항목: JS syntax check, 렌더링 확인
- 완료 조건: 전역 라벨/CTA가 고객 언어로 통일됨

## 작업 4. 가격/문서/가이드/사례 보조 페이지 판매형 정리
- 우선순위: 중간
- 목적: 보조 페이지에서도 전환 흐름이 끊기지 않게 만들기
- 원인: 설명형 보조 문구 과다
- 상세 조치: pricing/docs/guides/cases/product demo/plans/delivery/faq 헬퍼 문구 개편
- 대상 파일/영역: scripts/generate_compat_pages.py, build.py
- 영향 범위: 비교형/검토형 고객 흐름
- 검증 항목: 각 경로 200 응답 및 핵심 DOM 존재
- 완료 조건: 보조 페이지 카피 일관성 확보

## 작업 5. 검증 게이트 안정화
- 우선순위: 중간
- 목적: 잘못된 포트 충돌로 엉뚱한 서버를 검증하는 상황 방지
- 원인: package_completion_gate 고정 포트 사용
- 상세 조치: 사용 가능한 포트를 찾아 full/board 검증 수행하도록 수정
- 대상 파일/영역: scripts/package_completion_gate.py
- 영향 범위: 로컬 자동 검증
- 검증 항목: package_completion_gate 전체 통과
- 완료 조건: 포트 충돌 상황에서도 검증 안정성 확보

# F. 실제 반영 내용 또는 최종 개선안
- 무엇을 왜 바꾸는지:
  - 브랜드/회사/제품 카피를 내부 운영형 설명에서 판매형 메시지로 재작성
  - CTA를 "보기" 중심에서 "확인/진행" 중심으로 변경
  - 제품 4종의 headline/summary/value/output/FAQ/plan note를 구매 이유 중심으로 정리
  - 가격/문서/사례/가이드 보조 페이지까지 같은 톤으로 보정
  - package_completion_gate에 free-port 탐색 로직 추가
- 반영 대상:
  - src/data/site.json
  - build.py
  - scripts/generate_compat_pages.py
  - src/assets/site.js
  - scripts/package_completion_gate.py
- 기존 기능 영향:
  - 기능 로직은 유지
  - 공개 문구와 검증 유틸만 조정
- 주의사항:
  - 운영 서버 반영은 별도 배포 필요
  - live 결제/실도메인 검증은 미포함
- 추가/보완/강화 내용:
  - 카피 과다 중복 용어 감소
  - CTA 직관성 개선
  - 로컬 검증 포트 충돌 취약점 보완

# G. 테스트 계획 및 결과
- 수행한 테스트:
  - python3 -m py_compile build.py server_app.py start_server.py scripts/*.py
  - node --check src/assets/site.js
  - python3 build.py
  - python3 scripts/package_completion_gate.py
- 테스트 실행 상태: 실제 확인 완료
- 발견된 문제:
  - 초기 검증 중 package_completion_gate가 고정 포트 사용으로 잘못된 서버를 물 수 있는 취약점 확인
- 수정/개선/보완/추가/강화 내용:
  - free-port 탐색 로직 추가 후 전체 게이트 재실행
- 수정 후 재검증 결과:
  - full 모드 smoke/post-deploy/e2e/quality/api safety/deployment consistency/full audit 통과
  - board 모드 smoke/regression/full audit 통과
- 전역 테스트 결과:
  - full 검증 통과
  - board 검증 통과
- 납품 전 최종 검증 결과:
  - 로컬 기준 납품 가능 상태
- 스크립트 없음 항목:
  - 없음
- 환경 제약으로 실행 불가 항목:
  - 운영 도메인 실제 배포 반영 검증
  - Toss 실키 live 결제 검증
- 검증 미완료 항목:
  - Coolify 운영 서버 실제 반영 여부
  - 운영 SSL/canonical 실제 상태

# H. 남은 리스크
- 실제 남아 있는 리스크:
  1) 운영 서버에 아직 이 수정본이 배포되지 않았을 수 있음
  2) 실결제 1회 검증은 아직 안 됨
  3) 실제 도메인 캐시/CDN/프록시가 예전 정적 산출물을 물고 있을 수 있음
- 위험도: 중간
- 대응책:
  1) 수정본 배포
  2) 운영 도메인 smoke/post_deploy_verify 실행
  3) Toss live 소액 1회 검증
- 납품 영향도: 로컬 기준은 낮음, 실운영 반영 전까지는 중간

# I. 최종 인수 판단
- 즉시 검토 가능 여부: 가능
- 즉시 시연 가능 여부: 가능
- 즉시 인수 검토 가능 여부: 가능
- 즉시 납품 가능 여부: 로컬 기준 가능 / 운영 반영 기준은 미확정
- 추가 조치 필요 여부: 있음
- 판단 근거:
  - 공개 카피가 판매형 기준으로 재작성됨
  - 기능 로직은 유지됨
  - full/board 전역 검증 통과
  - 다만 운영 배포 반영과 실결제는 아직 확인되지 않음

# 전역 요소 기준 카피/전환 점검 항목 수
- 헤더/네비게이션/푸터/전역 라벨: 18건
- 홈/회사/제품 목록/콘텐츠 허브 상단 메시지: 26건
- 제품 4종 headline/summary/value/output/FAQ/plan note: 52건
- 데모/결제/문의/포털/결제 성공·실패: 21건
- 가격/문서/가이드/사례/보조 페이지: 24건
- 검증 게이트 취약점: 1건
- 합계: 142건
