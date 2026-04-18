# 데모 submit 동작 수정 검증

- 원인: `renderLiveStats` 함수가 정의되지 않은 상태에서 `DOMContentLoaded` 초기화 루틴이 중단되어 `bindDemoForm()`가 실행되지 않았습니다.
- 증상: `즉시 분석하기` 버튼 클릭 시 submit 핸들러가 바인딩되지 않아 현재 페이지 새로고침만 발생했습니다.
- 조치: `src/assets/site.js`, `dist/assets/site.js`에 `renderLiveStats()` 구현 추가
- 검증:
  - `node -c src/assets/site.js` 통과
  - `node -c dist/assets/site.js` 통과
  - `python -m py_compile build.py server_app.py start_server.py scripts/*.py` 통과
  - `renderLiveStats` 정의 존재 확인
  - `bindDemoForm` / `bindProductDemoForm` 초기화 호출 유지 확인
