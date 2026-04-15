# NV0 사업자정보 반영 및 런타임 검증 패치 보고서

## 이번 패치에서 반영한 내용
- 사업자등록증 기준 정보 반영
  - 상호: 엔브이제로(NV0)
  - 대표자: 나금상
  - 사업자등록번호: 584-77-00586
  - 개업연월일: 2026-03-15
  - 사업장 소재지: 경기도 남양주시 와부읍 덕소로97번길 34, 105동 402호(덕소주공아파트1단지)
  - 과세 유형: 일반과세자
  - 관할 세무서: 구리세무서
- 사업자등록증 이미지 파일 포함
  - src/assets/business-registration.png
  - dist/assets/business-registration.png
- 회사 페이지에 사업자 정보 카드 및 증빙 이미지 삽입
- 푸터 공통 고지에 상호/대표자/사업자등록번호/주소 반영
- 이용약관에 사업자등록번호 반영
- 개인정보처리방침/환불정책/쿠키 안내 페이지에 사업자 정보 추가 반영

## 수정 파일
- src/data/site.json
- src/assets/site.js
- src/assets/business-registration.png
- scripts/page_overrides.py
- dist/company/index.html
- dist/legal/privacy/index.html
- dist/legal/refund/index.html
- dist/legal/cookies/index.html
- dist/legal/terms/index.html
- dist/assets/business-registration.png

## 로컬 런타임 검증
실행 환경:
- PORT=8010
- NV0_TOSS_MOCK=1
- NV0_ALLOW_LOCAL_SCAN=1

검증 결과:
- GET / 200 OK 확인
- product_runtime_e2e.py 통과
- product_surface_regression.py 통과

## 중요한 한계
- 이 패키지는 코드/정적 산출물/로컬 런타임 기준으로는 정상 동작 검증을 마쳤습니다.
- 그러나 실제 운영 배포 후의 외부 인프라, DNS, SSL, 리버스 프록시, 실결제사 연동, 브라우저 캐시, CDN 캐시까지 포함한 절대적 의미의 "100%"는 배포 후 실환경 확인이 필요합니다.
