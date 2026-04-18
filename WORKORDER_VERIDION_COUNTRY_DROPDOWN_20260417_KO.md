# Veridion 주요운영국가 드롭다운 적용 작업지시서 및 처리결과

## 반영 목적
Veridion 데모 입력폼의 **주요운영국가**를 자유 입력이 아닌 드롭다운으로 고정하고, 기본값을 **대한민국(KR)** 으로 설정했습니다.  
동시에 이 선택값이 실제 분석 결과와 리포트 출력에도 반영되도록 서버 로직까지 함께 수정했습니다.

## 적용 범위
- `dist/products/veridion/demo/index.html`
- `src/assets/site.js`
- `dist/assets/site.js`
- `server_app.py`
- `src/data/site.json`
- `dist/assets/site-data.js`

## 반영 내용
1. 데모 입력폼의 `주요 운영 국가`를 텍스트 입력에서 드롭다운으로 변경
2. 기본 선택값을 `대한민국(KR)` 으로 설정
3. 프런트엔드에서 선택 국가를 `country` 코드와 `countryLabel`로 처리
4. 기존 `market` 흐름과도 호환되게 유지
5. 서버에서 국가 미입력/이상값일 때 `KR`로 자동 fallback
6. 국가별 법령 기준 요약을 분석 결과에 포함
7. 공개 리포트 응답에 아래 필드 추가
   - `country`
   - `countryLabel`
   - `legalBasis`
8. 데모 결과 화면에 `분석 기준 국가` 섹션 추가
9. Veridion 기본 데모 설정에 `country=KR` 반영
10. 정적 번들 `dist/assets/site-data.js` 재생성

## 드롭다운 옵션
- 대한민국 (기본값)
- 일본
- 미국
- 유럽연합
- 중국
- 동남아

## 서버 반영 방식
- `resolve_veridion_country(payload)` 추가
- `scan_cache_key()`에 국가코드 반영
- `build_veridion_scan()`에서 국가코드/국가명/법령기준을 리포트에 포함
- `build_veridion_public_report()` 및 `build_veridion_demo_preview()`에 관련 필드 노출

## 검증 결과
- `server_app.py` 파이썬 컴파일 통과
- 데모 HTML에 `country` 드롭다운 존재 확인
- 기본값 `KR/대한민국` 반영 확인
- 프런트 JS에서 국가값 fallback 및 결과 반영 로직 확인

## 비고
현재 국가별 법령 룰셋은 **기준 표시와 결과 분기 기반**까지 반영했습니다.  
국가별 세부 제재 계산식과 상세 조항 문구를 더 촘촘하게 분리하는 추가 고도화는 후속 확장으로 진행하면 됩니다.
