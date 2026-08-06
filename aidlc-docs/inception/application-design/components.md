# Components — coin-recommender

## Unit 1: data-pipeline

### MarketSelector (`market_selector.py`)
- **목적**: 업비트 KRW 마켓 중 추천 후보군 선정
- **책임**: 24시간 거래대금 상위 20개 알트코인(BTC/ETH 제외) 조회
- **인터페이스**: 마켓 코드 리스트를 반환 (외부에는 순수 조회 함수로 노출)

### UpbitClient (`upbit_client.py`)
- **목적**: 업비트 공개 API(pyupbit) 래핑
- **책임**: 후보 코인의 1시간봉/4시간봉 OHLCV 조회, 마켓별 24h 거래대금 조회(MarketSelector가 사용)
- **인터페이스**: 캔들 리스트, 티커/거래대금 정보 반환

### BinanceClient (`binance_client.py`)
- **목적**: 바이낸스 공개 API(`/api/v3/klines`) 래핑
- **책임**: BTC/ETH 4시간봉 원시 캔들 조회만 담당 (해석·지표 계산은 하지 않음 — 아래 "정정 사항" 참조)
- **인터페이스**: 캔들 리스트 반환

### DataStore (`data_store.py`)
- **목적**: SQLite 영속 계층
- **책임**: 캔들 upsert, 증분 수집 기준점(마지막 저장 시각) 조회, 저장된 캔들 조회
- **테이블**: `upbit_candles`, `binance_candles` (분리, unique key: market+timeframe+candle_time)

## Unit 2: analytics-backtest

### Features (`features.py`)
- **목적**: 일목균형표 계산 (순수 함수, 거래소 무관)
- **책임**: 전환선/기준선/스팬A/스팬B/후행스팬 계산, 구름 위치·색 판정
- **인터페이스**: 캔들 리스트 입력 → 지표가 포함된 데이터 반환

### Backtest (`backtest.py`)
- **목적**: 시그널 상태별 과거 실적 통계
- **책임**: 코인별로 동일 시그널 상태가 과거 발생했던 시점들의 실제 24시간 후 수익률 평균, 표본 수(N), 적중 횟수(24h 수익률 ≥ +4%) 산출
- **인터페이스**: (market, signal_state, 지표 포함 캔들) 입력 → 통계 결과 반환

### Scorer (`scorer.py`)
- **목적**: 최종 추천 리스트 산출
- **책임**:
  1. Binance BTC/ETH 캔들에 Features를 적용해 레짐(4h 구름 위/양운 여부) 판정 — 레짐이 조건 미충족이면 즉시 빈 추천 리스트 반환 (하드 필터)
  2. 각 알트 후보에 대해 4h 추세필터 + 1h 골든크로스로 현재 시그널 상태 판정
  3. Backtest로 코인별 기대수익률 조회
  4. 기대수익률 ≥ 4%인 코인만 최종 리스트에 포함 (N=0이면 제외)
- **인터페이스**: 추천 리스트(코인, 기대수익률, N, 적중횟수) 반환

## Unit 3: api-service

### Pipeline (`pipeline.py`)
- **목적**: 전체 파이프라인 오케스트레이션 (Application Design 질의응답으로 신규 추가 확정)
- **책임**: 후보군 조회 → 데이터 수집/저장 → Scorer 호출 → 결과 저장 → 알림 트리거를 순서대로 실행. `POST /run`과 Scheduler가 공유
- **인터페이스**: 실행 결과(추천 리스트 + 실행 메타데이터) 반환

### Scheduler (`scheduler.py`)
- **목적**: 자동 실행
- **책임**: APScheduler 설정 및 FastAPI lifespan 통합, 매시 정각 후 약 5분 지연으로 Pipeline 호출

### Notifier (`notifier.py`)
- **목적**: 외부 알림
- **책임**: 텔레그램/디스코드 웹훅으로 추천 결과(또는 "추천 없음") 전송

### API (`api.py`)
- **목적**: 외부 인터페이스
- **책임**: FastAPI 앱 정의, `GET /recommendations`, `POST /run`, `GET /health` 라우트, lifespan에서 Scheduler 시작/종료

## 정정 사항 (Application Design 중 발견)

원래 Application Design Plan에서는 레짐 하드필터를 `binance_client.py`에 두기로 사전 결정했으나, 컴포넌트 의존관계를 설계하는 과정에서 이 로직이 Unit 2의 `features.py`(일목균형표 계산)를 필요로 한다는 것을 확인했습니다. `binance_client.py`는 Unit 1에 속해 Unit 2보다 먼저 구현되므로, Unit 1 컴포넌트가 아직 존재하지 않는 Unit 2 컴포넌트를 참조하는 순서 역전이 발생합니다. 이를 피하기 위해 레짐 판정 로직을 `scorer.py`(Unit 2)로 이동했습니다 — `binance_client.py`는 원시 데이터 조회만 담당하도록 책임을 좁혔습니다. 이 정정에 동의하지 않으시면 "Request Changes"로 알려주세요.
