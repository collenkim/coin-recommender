# Code Generation Summary — Unit 1: data-pipeline

## Generated Files

### Application Code
- `src/config.py` — `Settings` (pydantic-settings, loads `config/settings.yaml` + `.env`, UTF-8 encoding explicit)
- `src/data_store.py` — `Candle`, `DataStore` (SQLite, WAL mode, upsert/get_candles/get_last_candle_time)
- `src/upbit_client.py` — `UpbitClient`, `TickerInfo` (get_ohlcv, get_tickers_by_volume, retry+backoff, KST→UTC normalization)
- `src/binance_client.py` — `BinanceClient` (get_klines, retry+backoff)
- `src/market_selector.py` — `MarketSelector` (top-20 by 24h volume, excludes BTC/ETH)
- `config/settings.yaml`, `.env.example`, `.gitignore`, `requirements.txt`, `README.md`

### Tests (`tests/`)
- `generators.py` — 공용 Hypothesis `Candle` 생성기 (PBT-07)
- `test_data_store.py` — CRUD/upsert 예시 테스트 6개 + PBT-02(라운드트립, 멱등성) 2개
- `test_upbit_client.py` — KST→UTC 변환, 빈 데이터, 재시도/포기, 티커 파싱 (7개)
- `test_market_selector.py` — BTC/ETH 제외, 상위 N 정렬, 빈 결과 (3개)
- `test_binance_client.py` — 파싱, startTime 파라미터, 5xx 재시도, 4xx 미재시도 (4개)

## 실행 검증 (실제 실행 완료)

이 머신에 Python 3.11+가 없어 `winget`으로 Python 3.11.9를 설치하고 `venv`를 생성해 실제로 실행했습니다 (사용자 승인 하에 진행).

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pytest -v
```

**결과**: 21개 테스트 전체 통과.

### 실행 중 발견하고 수정한 실제 버그 2건
1. **테스트 버그**: `test_get_ohlcv_retries_on_connection_error_then_succeeds`가 `time.sleep`이 재시도 백오프 1회만 호출된다고 가정했으나, 실제로는 그 뒤 rate-limit 지연(`request_delay_seconds`) 호출도 같은 `time.sleep`을 거쳐 2회 호출됨 — assertion을 백오프 호출값(1.0s) 확인으로 수정
2. **코드 버그**: `src/config.py`가 `config/settings.yaml`을 읽을 때 인코딩을 명시하지 않아, 한국어 Windows 환경(cp949 기본 인코딩)에서 UTF-8 파일의 한글 주석을 읽다가 `UnicodeDecodeError` 발생 — `yaml_file_encoding="utf-8"`을 `SettingsConfigDict`에 추가해 수정. (실제로 실행해보지 않았다면 사용자의 Windows 환경에서 그대로 재현되었을 버그)

## 아직 없는 것 (다음 유닛에서 추가)
- `pipeline.py`, `notifier.py`, `scheduler.py`, `api.py` (Unit 3)
- `features.py`, `backtest.py`, `scorer.py` (Unit 2)
- 이 유닛만으로는 독립 실행 가능한 엔트리포인트가 없음 (라이브러리 계층) — `pytest`로만 검증 가능, Unit 3 완료 후 API로 통합 실행
