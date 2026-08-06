# Requirements Clarification Questions — coin-recommender

주신 스펙은 매우 구체적이지만, 구현 방식이 갈리는 지점 몇 가지와 스펙 내부의 모순으로 보이는 부분이 있어 확인 후 진행하겠습니다. 각 질문에 [Answer]: 태그로 답변해주세요.

## Question 1: BTC/ETH 레짐 "페널티"의 정확한 계산 방식 (스펙 내 모순 확인)

스펙에서 "규칙기반 점수가 아니라 과거 실제 수익률 평균을 기대수익률로 계산"한다고 하셨는데, 동시에 "바이낸스 BTC/ETH 구름대가 하락이면 전체 알트 점수에 페널티"라고도 하셨습니다. 후자는 규칙 기반 감점처럼 보여 방식이 상충됩니다. 어느 쪽으로 구현할까요?

A) 레짐을 시그널 상태의 일부로 포함 — "BTC/ETH 4h 구름대 상태(상승/하락)"를 시그널 상태 정의에 포함시켜, 레짐이 하락일 때의 과거 사례만으로 별도 기대수익률을 계산 (완전히 데이터 기반, 규칙 기반 감점 없음)

B) 하드 필터 — BTC/ETH 4h 구름대가 하락이면 해당 시점엔 알트코인 추천을 아예 생성하지 않음 (점수 계산 자체를 스킵)

C) 명시적 수치 페널티 — 기대수익률 계산 후 레짐이 하락이면 고정 비율(예: -20%)을 곱하거나 차감 (규칙 기반 요소를 일부 허용)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2: 백테스트용 과거 데이터 수집 범위

일목균형표 계산에 필요한 부트스트랩은 타임프레임당 최소 100봉(4시간봉 기준 약 16.7일치)입니다. 하지만 "동일 시그널 상태의 과거 24시간 수익률 평균"을 신뢰성 있게 계산하려면 그보다 훨씬 긴 히스토리가 필요할 수 있고, 초기에는 표본 수(N)가 0~1개라 추천이 거의 나오지 않을 가능성이 높습니다. 어떻게 처리할까요?

A) 지표 계산용 100봉만 수집하고, 백테스트 표본은 매 실행마다 자연히 누적되는 것만 사용 (초기엔 추천이 거의 없거나 0개일 수 있음을 감수)

B) 지표 계산과 별도로, 백테스트 통계용으로 훨씬 긴 기간(예: 최근 6개월~1년치)의 과거 캔들을 추가로 한 번 수집해 초기 표본을 확보

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 3: 시그널 상태별 표본을 코인 단위로 볼지, 전체 알트 풀로 볼지

"동일 시그널 상태의 과거 수익률"을 계산할 때, 표본을 어느 범위에서 모을지 정해야 합니다. 코인 1개만 놓고 보면 특정 시그널이 몇 달에 한 번만 발생해 표본이 거의 없을 수 있습니다.

A) 코인별 개별 계산 — 해당 코인 자체의 과거 시그널 발생 사례만 사용 (코인마다 특성이 다르다는 전제, 다만 표본 부족 가능성 큼)

B) 전체 알트 후보군 풀링(pooled) — 후보군 20개 전체에서 동일 시그널이 발생했던 모든 과거 사례를 코인 구분 없이 합쳐서 계산 (표본 확보 유리, 코인별 특성 차이는 무시)

C) 코인별 계산을 우선하되, 해당 코인의 표본이 임계치(예: N<5) 미만이면 전체 풀 통계로 대체(fallback)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4: 알림(텔레그램/디스코드) 발송 조건

매 스케줄 실행 후 알림을 언제 보낼지 정해주세요.

A) 매 실행마다 항상 전송 (추천이 0개여도 "오늘은 추천 없음" 메시지 전송)

B) 추천 리스트가 1개 이상 있을 때만 전송

C) 직전 실행 대비 새로 추가된 추천 코인이 있을 때만 전송

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5: 스케줄러 실행 주기

"1시간봉/4시간봉 기준"이라 하셨는데, 자동 실행 타이밍을 정확히 언제로 할지 확인이 필요합니다.

A) 매시 정각 캔들 마감 후 일정 지연(예: 5분)을 두고 1시간마다 1회 실행 (1시간봉 갱신 기준)

B) 4시간봉 마감 시점(0, 4, 8, 12, 16, 20시 KST 등)에만 실행

C) 고정 간격(예: 15분마다)으로 실행하며 캔들 마감 여부와 무관하게 항상 최신 데이터 기준으로 재계산

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6: GET /recommendations 응답 범위

A) 가장 최근 1회 실행의 추천 리스트만 반환 (단순)

B) 최신 결과 + 쿼리 파라미터로 과거 실행 이력도 조회 가능하게 지원 (예: `?limit=N` 또는 날짜 지정)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7: API 노출/인증 범위

이 서비스가 로컬에서만 개인적으로 쓰이는지, 외부에 노출될 가능성이 있는지에 따라 인증 필요 여부가 달라집니다.

A) 로컬/개인 사용 전용, 인증 없이 진행 (PoC/개인 프로젝트 단계)

B) 향후 외부 노출을 고려해 최소한의 인증(API Key 등)을 처음부터 포함

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question: Security Extensions

Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question: Resiliency Extensions

Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of directional, design-time best practices for building resilient systems (AWS Well-Architected Framework Reliability Pillar), covering fault tolerance, availability, observability, and recoverability.

**What this extension is NOT.** It does not certify production-readiness or guarantee any availability/RTO/RPO target — it's a starting point, not a substitute for a formal Well-Architected Review.

A) Yes — apply the resiliency baseline as directional best practices (recommended for business-critical workloads)

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects where rapid iteration matters more than reliability)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question: Property-Based Testing Extension

Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended given this project has non-trivial business logic: ichimoku feature calculation, expected-return backtest statistics)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips (e.g., ichimoku calculations) but not the whole system

C) No — skip all PBT rules

X) Other (please describe after [Answer]: tag below)

[Answer]: B
