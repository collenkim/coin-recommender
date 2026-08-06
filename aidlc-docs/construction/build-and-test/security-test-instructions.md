# Security Test Instructions

Security Baseline 확장이 활성화되어 있어(SECURITY-08 인증만 예외), 아래 항목을 확인합니다.

## 1. 시크릿 하드코딩 확인 (SECURITY-12)
```bash
git grep -inE "(bot_token|webhook|api[_-]?key|secret)\s*=\s*['\"]" -- src/ config/
```
- **기대**: 코드/설정 파일에 실제 값이 하드코딩되어 있지 않음 (모두 `.env`에서 로드)
- **실측 확인**: `src/config.py`의 시크릿 필드는 전부 `None` 기본값, `.env.example`도 값이 비어있음 — 통과

## 2. `.env`가 커밋되지 않는지 확인
```bash
git status --ignored | grep "\.env$"
```
- **기대**: `.env`가 `.gitignore`에 의해 무시됨 (`.gitignore`에 포함되어 있음, 실제 `.env` 파일은 아직 생성되지 않은 상태)

## 3. 의존성 고정 확인 (SECURITY-10)
```bash
cat requirements.txt
```
- **기대**: 모든 의존성 버전 고정
- **실측 확인**: 초안에서는 `fastapi`/`uvicorn`/`apscheduler`/`httpx`가 미고정 상태였음 — Build and Test 단계에서 발견 후 실제 설치된 버전으로 고정 완료

## 4. 에러 응답에 내부 정보 노출 여부 (SECURITY-09)
`tests/test_api.py::test_unhandled_exception_returns_generic_500_body`가 이미 자동 검증 — 내부 예외 메시지가 응답 본문에 노출되지 않음을 확인함

## 5. 입력 검증 (SECURITY-05)
현재 엔드포인트는 사용자 입력 파라미터가 거의 없어(전부 파라미터 없는 GET/POST) 표면적이 작음 — 향후 쿼리 파라미터 추가 시 pydantic 모델로 검증할 것

## 인증 관련 (SECURITY-08 예외 재확인)
이 서비스는 인증이 없습니다. **외부 인터넷에 노출하지 마세요** (로컬/개인 사용 전제 — Requirements Analysis에서 확정된 전제). 외부 노출이 필요해지면 이 문서와 requirements.md의 관련 결정을 재검토해야 합니다.
