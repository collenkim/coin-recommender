# Functional Design Plan — Unit 1: data-pipeline

## Plan
- [x] Generate `business-logic-model.md` — 후보군 선정, 부트스트랩/증분 수집, upsert 흐름
- [x] Generate `business-rules.md` — 데이터 검증/제외 규칙, 타임스탬프 정규화, 부분 실패 처리
- [x] Generate `domain-entities.md` — Candle, TickerInfo 등 도메인 모델

## Question Category Evaluation

Unit 1의 책임(후보군 선정, 캔들 수집, upsert 저장)에 대해 아래 카테고리를 검토했습니다. 대부분 requirements.md/application-design에서 이미 결정되었거나, 명백한 기술적 모범사례로 판단할 수 있는 항목이라 **새 질문 없이 아래와 같이 결정**하고 산출물에 근거를 명시합니다.

| 카테고리 | 결정 | 근거 |
|---|---|---|
| 타임스탬프 정규화 | 모든 `candle_time`은 UTC로 저장 | 업비트/바이낸스 두 출처를 일관되게 비교·조인해야 함. 로컬/거래소별 타임존 혼용은 버그 유발 가능성 큼 — 표준 관행 채택 |
| 신규 상장 코인(캔들 부족) | 부트스트랩 시 100봉 미만이면 해당 회차 후보에서 제외, 로그 남기고 계속 진행 | 예견 가능한 실제 시나리오(신규 상장 코인은 자연히 발생) — Resiliency graceful degradation 원칙과 일관 |
| 업비트 API 레이트리밋 | 마켓별 순차 호출 + 짧은 지연(구체 수치는 NFR Design에서 확정) | pyupbit 공개 API에 요청 제한 존재, 20개 마켓 x 2타임프레임 순회 시 고려 필요 — 정확한 값/재시도 정책은 NFR Design 단계 소관이라 여기서는 흐름만 정의 |
| 백테스트용 장기 이력과 지표용 100봉의 관계 | 동일 upsert 대상 테이블/유니크 키 사용 — 자연스럽게 중복 제거 | FR3에서 이미 두 수집을 "같은 저장 계층"으로 명시, 별도 테이블 불필요 |

질문이 없으므로 바로 산출물을 생성합니다.
