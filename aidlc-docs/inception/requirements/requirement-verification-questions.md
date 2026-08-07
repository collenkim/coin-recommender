# Requirements Clarification Questions — 추천 결과 적중 판별 및 학습 반영

현재 로직을 확인한 결과를 먼저 공유합니다: 지금 `expected_return`/`n`/`hit_count`는 **순전히 과거 데이터 기반 회고적 계산**입니다 (`src/backtest.py`의 `compute_signal_stats`) — 추천 시점에 그 코인의 과거 캔들 히스토리에서 "같은 시그널이 떴던 과거 시점들"을 찾아, 그때의 실제 24시간 후 수익률을 평균낸 것입니다. 추천을 저장한 뒤 "이 추천이 실제로 적중했는지"를 나중에 다시 확인하는 로직은 전혀 없습니다 (`recommendations` 테이블에 추천만 쓰고 끝).

아래 질문들이 구현 방향을 가르는 지점입니다.

## Question 1
"예측 도달 %에 부합했는지"를 판별하는 기준은 무엇인가요?

A) 추천 시점 종가 대비 정확히 24시간 후 종가로 수익률 계산 (현재 백테스트 샘플과 동일한 방식 — `entry_close` vs `entry_close + 24봉`)

B) 24시간 이내 어느 시점에서든 (구간 내 고가 기준) 임계값(4%)에 도달했으면 적중으로 판단 (더 관대한 기준, 실제 트레이더가 "익절"하는 방식에 가까움)

C) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
"학습해서 더 정교하게 맞춘다"는 구체적으로 어떻게 반영되길 원하시나요?

A) 판별된 적중/실패 결과를 기존 백테스트 샘플 풀에 새로운 실측 샘플로 누적 반영 — 시간이 지날수록 `expected_return`/`n`/`hit_count` 계산이 실제 라이브 데이터까지 포함해 더 정확해짐 (기존 회고적 백테스트 로직의 자연스러운 확장, 필터링 알고리즘 자체는 안 바뀜)

B) A에 더해, 마켓/시그널별 최근 적중률이 기준 이하로 떨어지면 해당 마켓을 추천 후보에서 자동 제외하거나 임계값을 동적으로 조정하는 적응형 필터링까지 추가

C) 지금은 판별 결과를 기록하고 API로 조회만 가능하게 하고, 추천 로직에 자동 반영하는 건 나중에 별도로 진행

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
적중 여부 판별은 언제 실행되나요?

A) 기존 시간당 스케줄러(매시 5분, `src/scheduler.py`) 실행 안에서, 24시간이 지나 아직 판별 안 된 과거 추천 건들을 함께 처리

B) 별도의 독립적인 스케줄/트리거로 분리

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
이 기능 배포 이전에 이미 저장된 과거 추천 기록(`recommendations` 테이블 기존 데이터)도 소급 판별할까요?

A) 배포 이후 새로 생성되는 추천부터만 적용 (과거 기록은 그대로 미판별 상태로 둠)

B) DB에 필요한 캔들 데이터가 남아있다면 과거 기록도 소급 판별해서 채움

C) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
판별 결과(적중/실패, 실제 수익률)를 API로도 노출할까요? (`GET /recommendations` 확장 또는 신규 엔드포인트)

A) 네, `GET /recommendations`에 과거 추천들의 판별 결과(적중 여부, 실제 수익률)를 포함해서 보여준다

B) 네, 하지만 별도의 신규 엔드포인트로 (예: `GET /recommendations/history` 또는 `GET /accuracy`)

C) 아니요, 지금은 내부 데이터로만 쌓고 API 노출은 필요 없음

D) Other (please describe after [Answer]: tag below)

[Answer]: A
