# 최종 보강 메모 (2026-04-19)

이번 보강에서 실제 사용자 체감에 직접 영향 주는 데모 파이프라인을 다시 묶었습니다.

## 수정 사항
- product demo submit 흐름에서 제품 객체를 더 안전하게 추론하도록 보강
- 원격 분석 호출에 20초 timeout 추가
- 원격 분석 실패(remote-failed) 시 조용히 멈추지 않고 fallback 사유를 화면에 노출
- Veridion/기타 제품 모두 결과 박스에 반드시 상태 또는 결과가 남도록 보강
- 결과 렌더 후 결과 박스로 자동 스크롤되도록 보강
- 데모 실행 시 최근 분석 컨텍스트를 항상 rememberDemoFlow에 저장하도록 보강

## 검증
- node --check src/assets/site.js
- node --check dist/assets/site.js
- smoke_release.py --mode full
- veridion_runtime_regression.py
- product_surface_regression.py

## 기대 효과
- "버튼은 눌렸는데 아무 일도 안 보이는 상태"를 줄임
- 원격 API가 느리거나 실패해도 프리뷰 결과와 사유를 먼저 표시
- 이후 checkout / portal 연계에 필요한 최근 컨텍스트 보존 강화
