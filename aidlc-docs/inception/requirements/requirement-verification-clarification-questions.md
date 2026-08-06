# Requirements Clarification Questions — Round 2 (Contradiction/Scope Check)

답변 감사합니다. 검토 중 답변들 사이에서 **모순 1건**과 **범위 불일치 1건**을 발견해서, 추측으로 넘어가지 않고 확인받고자 합니다.

## Contradiction 1: Security Baseline 전체 강제 적용 vs "인증 없음"

Security Extensions 질문에서 "A) 전체 SECURITY 규칙을 blocking 제약으로 강제 적용"을 선택하셨습니다(Q: Security Extensions, Answer: A). 그런데 API 노출/인증 범위 질문(Question 7)에서는 "A) 로컬/개인 사용 전용, 인증 없이 진행"을 선택하셨습니다.

Security Baseline의 **SECURITY-08 규칙**은 "모든 라우트/엔드포인트는 명시적으로 public으로 표시되지 않는 한 기본적으로 인증을 요구해야 한다(deny by default)"를 blocking 요구사항으로 규정합니다. 이걸 그대로 강제하면 `GET /recommendations`, `POST /run` 모두 인증이 필요해져서, Question 7의 "인증 없이" 답변과 정면으로 충돌합니다.

### Clarification Question 1

A) 로컬/개인용 유지, SECURITY-08만 예외 처리 — Security Baseline은 계속 강제 적용하되, SECURITY-08(인증)만 "N/A — 로컬 개인 사용, 외부 미노출"로 문서화하고 나머지 규칙(입력 검증, SQL 인젝션 방지, 에러 처리, 시크릿 관리, 로깅 등)은 그대로 적용

B) 인증 추가 — 처음부터 간단한 API Key 인증(헤더 기반)을 넣어서 SECURITY-08까지 포함해 전체 규칙을 예외 없이 적용

C) Security Baseline 비활성화 — 전체 확장을 끄고, 상식적인 보안 위생(하드코딩된 시크릿 금지, SQL 인젝션 방지, 에러 메시지에 내부 정보 노출 금지)만 확장 없이 자연스럽게 적용

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Scope Mismatch 2: Resiliency Baseline 전체 강제 적용 vs 로컬 단일 사용자 규모

Resiliency Extensions 질문에서도 "A) 전체 규칙을 blocking 제약으로 강제 적용"을 선택하셨습니다. 하지만 Resiliency Baseline을 전체 적용하면, 확장 규칙 자체에 명시된 대로 다음 항목들을 **먼저 사용자가 결정**해야 합니다:

- RTO/RPO 목표 및 재해복구(DR) 전략 (Backup&Restore ~ Active/Active)
- 변경관리 프로세스 (기존 조직 프로세스 vs 신규 제안)
- CI/CD 툴링 및 배포 방식 (blue/green, canary 등)
- 롤백 메커니즘
- 멀티 AZ / 멀티 리전 배포 토폴로지
- 카오스 엔지니어링 / DR 테스트 방식
- 장애 대응(Incident Response) 프로세스

이 항목들은 모두 **클라우드에 배포되는 프로덕션 워크로드**를 전제로 합니다. 현재 스펙은 로컬(또는 개인 서버) 1대에서 FastAPI + SQLite로 돌아가는 개인용 자동화 도구로, 멀티리전이나 공식 DR 전략, 변경관리위원회 같은 개념이 적용되지 않을 가능성이 높습니다. 어떻게 진행할까요?

### Clarification Question 2

A) 전체 유지 — 말씀하신 대로 프로덕션급 Resiliency Baseline을 전체 적용 (위 DR/멀티리전/변경관리 질문들에 이어서 답변하겠습니다)

B) 코드 레벨만 적용 — 클라우드 인프라 관련 항목(DR 전략, 멀티리전, 오토스케일링, 변경관리, 카오스 테스트 등)은 "N/A — 로컬 단일 인스턴스, 클라우드 미배포"로 문서화하고, 코드 레벨에서 실질적으로 의미 있는 항목만 적용: 외부 API(업비트/바이낸스/웹훅) 호출에 타임아웃 설정, 실패 시 재시도/백오프, 일부 실패해도 나머지는 계속 진행하는 graceful degradation, `/health` 헬스체크 엔드포인트

C) Resiliency Baseline 비활성화 — 지금 단계에서는 끄고, 실제 배포 환경이 정해지면 그때 다시 검토

X) Other (please describe after [Answer]: tag below)

[Answer]: B
