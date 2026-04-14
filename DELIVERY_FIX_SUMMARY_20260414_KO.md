# NV0 수정 납품 요약 (2026-04-14)

## 이번 납품에서 반영한 핵심 수정
1. `requirements.txt`에 `beautifulsoup4==4.14.2` 추가
   - Coolify 배포 컨테이너에서 `ModuleNotFoundError: No module named 'bs4'`로 즉시 종료되던 문제를 직접 해결했습니다.

2. `server_app.py`의 BeautifulSoup 파서 예외 처리 보강
   - 기존: `BeautifulSoup(..., 'lxml')`
   - 변경: `lxml` 파서를 우선 시도하고, 환경에 없으면 `html.parser`로 자동 폴백
   - 효과: `bs4`만 설치된 환경에서도 Veridion 스캔 기능이 파서 누락 때문에 죽지 않도록 보강했습니다.

3. `scripts/post_deploy_verify.py`를 현재 실제 빌드 산출물과 일치하도록 수정
   - 홈/엔진/제품 상세 페이지의 검증 마커가 구버전 템플릿 기준으로 남아 있어 패키지 완료 게이트가 실패하던 문제를 수정했습니다.
   - 현재 `dist/` 구조와 일치하는 검증 포인트로 재정렬했습니다.

## 확인한 검증 결과
### full mode
- `scripts/preflight_env.py` 통과
- `scripts/smoke_release.py --mode full` 통과
- `scripts/post_deploy_verify.py` 통과
- `scripts/product_runtime_e2e.py` 통과
- `scripts/result_quality_gate.py` 통과
- `scripts/api_safety_regression.py` 통과
- `scripts/deployment_consistency_check.py` 통과
- `scripts/full_audit.py --mode full` 실행 완료

### board-only mode
- `scripts/preflight_env.py` 통과
- `scripts/smoke_release.py --mode board` 통과
- `scripts/board_mode_regression.py` 통과
- `scripts/full_audit.py --mode board` 실행 완료

## 사전 차단/예상 문제 대응
1. **패키지 누락 재발 방지**
   - `bs4` import만 있고 설치 정의가 없던 상태를 해소했습니다.

2. **파서 의존성 차이 흡수**
   - `lxml` 미설치 환경에서도 크래시 없이 동작하도록 폴백 처리했습니다.

3. **검증 스크립트-실제 화면 불일치 해소**
   - 배포 후 검증이 코드 문제 없이도 오탐으로 실패하던 상태를 정리했습니다.

4. **기본 납품 상태는 full mode로 복원**
   - board-only 검증 후 다시 full build로 되돌려 납품했습니다.

## 납품물 구성
- 수정 반영 전체 소스 패키지 (감사/검증 포함)
- 배포용 패키지 (비밀값 안전 기준)
- full/board 감사 리포트 별도 보관
- 수정 요약 문서 포함

## 실운영에서 마지막으로 확인할 것
1. 실제 Coolify 환경변수에 `NV0_ADMIN_TOKEN`, `NV0_BACKUP_PASSPHRASE`, `FORWARDED_ALLOW_IPS`가 정확히 들어가 있는지
2. 실결제를 열 경우 `NV0_TOSS_MOCK=0`과 Toss live 키/웹훅 시크릿이 모두 맞는지
3. 도메인/프록시가 바뀌면 `NV0_BASE_URL`, `NV0_ALLOWED_HOSTS`, `NV0_ALLOWED_ORIGINS`, canonical 설정이 동일하게 맞는지

## 바로 재배포 권장 포인트
- 기존 실패 이미지를 재사용하지 않도록 Coolify에서 **캐시 없이 재빌드** 권장
- 새 커밋 기준으로 재배포 후 `/readyz`, `/api/health` 우선 확인
