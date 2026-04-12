# NV0 납품 변경 기록 (2026-04-12)

## 이번 정리 내용
- board-only 기준으로 남아 있던 문서를 현재 full package 기준으로 전면 교체
- 납품용 패키지 생성 스크립트 추가
- 배포 후 full/board 스모크 테스트 스크립트 추가
- clean manifest / checksum 생성 흐름 추가
- Docker build context 정리
- Makefile에 release/smoke 명령 추가

## 목적
- 납품물 혼선 제거
- 배포 직후 검증 시간을 단축
- 큰 용량의 불필요 파일 없이 필요한 실행 파일만 전달
- 실결제 전환 전/후 체크리스트를 명확히 유지

## 선제 보완 추가
- 이메일/조회코드 정규화로 포털 조회 실패 가능성 축소
- double submit 방지와 결제 설정 미완료 조기 차단 추가
- webhook fingerprint 중복 감지 추가
- 프록시 환경 canonical redirect 보강
- .env.example / preflight 규칙 동기화
