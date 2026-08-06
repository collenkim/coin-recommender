# Code Generation Plan — Unit 1: data-pipeline

## Unit Context
- **Stories/Requirements**: FR1(후보군), FR2(수집), FR3(부트스트랩/증분), FR4(저장)
- **Dependencies**: 없음 (Unit 1은 최하위 유닛)
- **Workspace Root**: `C:\Users\김우석(카이)\IdeaProjects\coin-recommend`
- **코드 조직**: `unit-of-work.md`에서 확정한 평면 `src/` 구조 (유닛별 서브디렉토리 없음)

## 원래 9개 파일 구조 대비 추가 파일 (근거 명시)

원래 요청하신 구조에는 없었지만, 사용자가 명시적으로 요청한 `pydantic-settings` 라이브러리를 쓰려면 `Settings` 클래스를 어딘가에 둬야 합니다. 여러 모듈(이번 유닛의 DB 경로/수집 파라미터, 다음 유닛들의 임계값/웹훅 URL 등)이 공유할 설정이라 개별 파일에 중복 정의하는 대신, 작은 공용 모듈 하나를 추가합니다:

- `src/config.py` — `pydantic-settings` 기반 `Settings` 클래스 (앞으로 유닛 진행하며 필드 계속 추가됨)
- `tests/generators.py` — Hypothesis용 공용 `Candle` 생성기 (PBT-07 재사용성 요구사항, Unit 2/3 테스트도 재사용 예정)

## Plan

### Step 1: Project Structure & Config Setup
- [x] `config/settings.yaml` 생성 (Unit 1 관련 필드: db_path, top_n_candidates, bootstrap_min_candles, backtest_lookback_days, http_timeout_seconds, http_max_retries, upbit_request_delay_seconds)
- [x] `.env.example` 생성 (현재는 비어있음 — 웹훅 시크릿은 Unit 3에서 추가)
- [x] `.gitignore` 생성 (`.env`, `data/`, `__pycache__/`, `*.db` 등)
- [x] `requirements.txt` 생성 (Unit 1 기준: pyupbit, requests, pydantic-settings, python-dotenv, pyyaml, pytest, hypothesis — 이후 유닛에서 계속 추가)
- [x] `src/config.py` 생성 — `Settings(BaseSettings)`
- [x] `README.md` 생성 (프로젝트 개요, 설치/실행 방법 — 이후 유닛에서 계속 보강)
- [x] `src/__init__.py`, `tests/__init__.py` 생성

### Step 2: Repository Layer — DataStore
- [x] `src/data_store.py` 생성: 스키마 초기화(`upbit_candles`, `binance_candles` 테이블, WAL 모드), `upsert_candles`, `get_last_candle_time`, `get_candles`

### Step 3: Repository Layer Testing
- [x] `tests/generators.py` 생성 — Hypothesis `candle_strategy()`
- [x] `tests/test_data_store.py` 생성 — 예시 기반 CRUD/upsert 테스트 + PBT-02(라운드트립), 멱등성 프로퍼티 테스트

### Step 4: Business Logic — Clients & Selector
- [x] `src/upbit_client.py` 생성: `get_ohlcv`, `get_tickers_by_volume`, 재시도 유틸
- [x] `src/binance_client.py` 생성: `get_klines`, 재시도 유틸
- [x] `src/market_selector.py` 생성: `get_candidate_markets`

### Step 5: Business Logic Testing
- [x] `tests/test_upbit_client.py` — HTTP 호출 mock, 부트스트랩/증분 분기, 재시도 동작 테스트
- [x] `tests/test_binance_client.py` — HTTP 호출 mock, 재시도 동작 테스트
- [x] `tests/test_market_selector.py` — BTC/ETH 제외, 상위 20개 선정 로직 테스트

### Step 6: Documentation Summary
- [x] `aidlc-docs/construction/data-pipeline/code/summary.md` 생성 — 생성된 파일 목록, 실행/테스트 방법 요약

### Step 7: Verify
- [x] 중복 파일 없는지 확인 (그린필드라 해당 없음, 형식상 확인)
- [x] 모든 체크박스 [x] 확인
