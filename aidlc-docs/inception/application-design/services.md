# Services — coin-recommender

이 프로젝트는 단일 FastAPI 프로세스로 배포되는 모놀리식 서비스이므로, 별도의 마이크로서비스 계층은 없습니다. 오케스트레이션을 전담하는 서비스 하나만 정의합니다.

## Pipeline Service (`pipeline.py`)

**책임**: 추천 계산 전체 흐름을 조율하는 유일한 오케스트레이션 지점

**오케스트레이션 순서**:
1. `MarketSelector.get_candidate_markets()` — 후보 20개 알트코인 조회
2. `UpbitClient.get_ohlcv()` + `DataStore.upsert_candles()` — 후보 코인 1h/4h 캔들 수집·저장 (부트스트랩 또는 증분)
3. `BinanceClient.get_klines()` + `DataStore.upsert_candles()` — BTC/ETH 4h 캔들 수집·저장
4. `Scorer.generate_recommendations()` — 레짐 확인 → 시그널 판정 → 기대수익률 계산 → 필터링
5. 추천 결과를 `DataStore`에 저장 (최신 실행 결과로 `GET /recommendations`가 조회)
6. `Notifier.send_notification()` — 결과를 텔레그램/디스코드로 전송 (항상 전송)

**호출자**:
- `POST /run` (API 핸들러가 직접 호출)
- `Scheduler`의 등록된 잡 (매시 정각+5분)

**설계 근거**: `POST /run`과 자동 스케줄 실행이 동일한 로직을 중복 구현하지 않도록 단일 진입점으로 통합 (Application Design 질의응답에서 확정, 옵션 B)

**부분 실패 처리 (RESILIENCY-10, graceful degradation)**: 특정 코인의 데이터 수집이 실패해도 파이프라인 전체를 중단하지 않고 해당 코인만 이번 회차 추천 대상에서 제외한 채 나머지를 계속 진행합니다. Binance 레짐 데이터 수집 자체가 실패하면(BTC/ETH는 필수 참조 데이터이므로) 안전하게 이번 회차를 스킵하고 빈 추천 리스트로 처리합니다.
