# NV0 작업지시서 정식본

## 작업명
NV0 공개 사이트/제품 런타임 전면 보정, SSR 강화, 정책 고지 강화, 로컬 검증 정상화

## 작업목적
- 제품 페이지 빈 상태 제거
- 공개 신뢰 페이지 보강
- 로컬/사전검증 단계 실행 불능 제거
- 패키지 단독 실행성과 테스트 일관성 확보

## 작업범위
1. `scripts/page_overrides.py`
   - 핵심 공개 페이지를 개선본으로 실제 dist에 overwrite
   - 제품 상세 SSR 출력 강화
2. `scripts/generate_compat_pages.py`
   - 개인정보처리방침/환불정책/쿠키 안내 문서 확장
3. `server_app.py`
   - Veridion 로컬 스캔 허용 조건 보강
4. `.env.local`, `.env.example`
   - 로컬 즉시 실행 기준값 반영
5. `scripts/site_issue_inventory.py`
   - 감지 가능 문제 계수화 도구 추가

## 완료기준
- 제품 상세 주요 정보가 정적 HTML만으로도 표시될 것
- 정책 페이지에 목적/항목/보관/권리/환불 기준이 명시될 것
- localhost 기준 Veridion 회귀 테스트가 통과할 것
- full smoke 및 제품 E2E가 통과할 것
- 감지 가능 정적 문제 수가 0건일 것

## 검수체크리스트
- [x] 제품 페이지 H1/리드/행동버튼 정적 출력
- [x] 제품 workflow/outputs 정적 출력
- [x] 회사 페이지 운영 정보 출력
- [x] 개인정보처리방침 보강
- [x] 환불정책 보강
- [x] 쿠키/저장 안내 보강
- [x] 로컬 스캔 회귀 복구
- [x] 로컬 env 즉시 실행 가능 상태 정리
- [x] smoke test 통과
- [x] product runtime e2e 통과
- [x] veridion runtime regression 통과
- [x] 감지 가능 문제 0건
