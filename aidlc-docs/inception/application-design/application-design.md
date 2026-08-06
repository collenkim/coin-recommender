# Application Design — coin-recommender (Consolidated)

이 문서는 다음 4개 문서를 통합합니다: `components.md`, `component-methods.md`, `services.md`, `component-dependency.md`. 전체 내용은 각 파일을 참조하세요.

## Summary

- **컴포넌트 11개** (원래 9개 파일 + 오케스트레이션 신규 `pipeline.py` + 기존 파일 내 세분화 없음), 3개 유닛으로 그룹화
- **오케스트레이션**: `Pipeline` 서비스 단일 진입점, `POST /run`과 `Scheduler`가 공유 (Application Design 질의응답에서 확정)
- **설계 중 정정 1건**: 레짐 필터 로직을 `binance_client.py` → `scorer.py`로 이동 (Unit 순서 역전 방지, `components.md` 참조)
- **의존관계**: Unit 1 → Unit 2 → Unit 3 단방향, 순환 의존 없음 (역전 없음 확인 완료, `component-dependency.md` 참조)

## Extension Compliance Summary

| Rule | Status | Rationale |
|---|---|---|
| SECURITY-12 (자격증명 관리) | Compliant | 웹훅 URL은 `.env` 분리 로드로 설계 확정, `settings.yaml`에는 비민감 값만 |
| RESILIENCY-06 (헬스체크) | Compliant | `API.GET /health` 컴포넌트 메서드로 설계 포함 |
| RESILIENCY-10 (타임아웃/재시도/우아한 성능 저하) | Compliant | `services.md`에 부분 실패 처리 정책 명시 (코인별 실패 격리, 레짐 데이터 실패 시 안전 스킵) — 구체적 타임아웃 값/재시도 횟수는 NFR Design(유닛별)에서 확정 |
| SECURITY-01/02/04/06/07/08/09/10/11/13/14/15, RESILIENCY-01~05/07~09/11~15, PBT-01~10 | N/A at this stage | 코드/인프라가 아직 생성되지 않았거나(SECURITY-09/15 등은 Code Generation 단계), 클라우드 인프라 자체가 N/A(요구사항 단계에서 확정)이거나, PBT-01은 Functional Design 단계 적용 대상이므로 이 단계에서는 평가 대상 아님 |

## Detail Documents

- [components.md](components.md) — 컴포넌트 정의 및 책임 (정정 사항 포함)
- [component-methods.md](component-methods.md) — 메서드 시그니처
- [services.md](services.md) — Pipeline 오케스트레이션 서비스
- [component-dependency.md](component-dependency.md) — 의존관계 매트릭스 및 데이터 흐름
