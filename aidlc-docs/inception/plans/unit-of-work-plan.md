# Unit of Work Plan — coin-recommender

## Plan

- [x] Generate `unit-of-work.md` — 유닛 정의, 책임, 코드 조직 전략
- [x] Generate `unit-of-work-dependency.md` — 유닛 의존관계 매트릭스
- [x] Generate `unit-of-work-story-map.md` — 요구사항 → 유닛 매핑 (User Stories가 스킵되었으므로 스토리 대신 requirements.md의 FR 항목을 매핑)
- [x] 유닛 경계/의존관계 검증
- [x] 모든 요구사항이 유닛에 매핑되었는지 확인

## Question Category Evaluation

이미 Workflow Planning(execution-plan.md)과 Application Design(component-dependency.md)에서 유닛 분해와 의존관계가 확정되어 있으므로, 아래 카테고리를 검토한 결과 **추가로 물어볼 질문이 없습니다** (근거 명시):

| 카테고리 | 평가 | 근거 |
|---|---|---|
| Story Grouping | N/A | User Stories 단계 스킵됨 (개인 단일 사용자) — 대신 요구사항(FR1~FR14)을 유닛에 매핑 |
| Dependencies | 이미 확정 | `component-dependency.md`에서 Unit1→Unit2→Unit3 단방향 의존, 순환 없음 검증 완료 |
| Team Alignment | N/A | 개인 프로젝트, 단일 개발자 — 팀 구조/오너십 분리 불필요 |
| Technical Considerations (배포/스케일링) | N/A | 3개 유닛 모두 단일 FastAPI 프로세스로 함께 배포 (모놀리식), 유닛별 개별 배포/스케일링 없음 (요구사항 분석에서 클라우드 미배포 확정) |
| Business Domain | 이미 명확 | 데이터 수집(Unit1) / 분석·백테스트(Unit2) / 서비스 노출(Unit3)로 자연스럽게 구분되는 bounded context |
| Code Organization (Greenfield) | 이미 확정 | 사용자가 원래 요청에서 `src/` 하위 평면(flat) 구조를 명시 — 유닛은 물리적 디렉토리 분리가 아닌 **설계+구현+검증 체크포인트 단위**로만 사용. `src/`는 평면 구조 유지 |

질문이 없으므로 바로 승인을 요청합니다.

## Approval Request

**Unit of work plan complete. Review the plan in `aidlc-docs/inception/plans/unit-of-work-plan.md`. Ready to proceed to generation?**
