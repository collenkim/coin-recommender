# Integration Test Instructions

## Purpose
유닛 간 상호작용(Unit 1 데이터 → Unit 2 분석 → Unit 3 오케스트레이션/API)이 실제로 맞물려 동작하는지 검증.

## 자동화된 통합 테스트 (이미 존재)
- `tests/test_pipeline.py`: Pipeline이 MarketSelector/Upbit/BinanceClient/Scorer/DataStore/Notifier를 올바른 순서로 호출하는지 (외부 I/O는 mock)
- `tests/test_api.py`: API 엔드포인트가 Pipeline/DataStore와 올바르게 연결되는지 (`TestClient` 사용, 외부 I/O는 mock)

이 두 파일이 사실상 "유닛 간 배선(wiring)"에 대한 통합 테스트 역할을 합니다. 외부 거래소 API는 개인 프로젝트 규모에서 CI성 자동 통합 테스트에 포함시키기엔 (a) 실제 네트워크 의존성, (b) 매 실행마다 시장 데이터가 달라 결과를 assert하기 어려움 — 두 가지 이유로 제외했습니다. 대신 아래 수동 라이브 검증 절차로 다룹니다.

## 수동 라이브 통합 검증 (실제 거래소 API 사용, Build and Test 단계에서 실제로 수행 완료)

### 1. 서버 기동
```bash
venv\Scripts\uvicorn src.api:app --port 8123
```

### 2. 헬스체크
```bash
curl http://127.0.0.1:8123/health
# 기대: {"status":"ok","db_connected":true}
```

### 3. 수동 파이프라인 실행 (실제 업비트/바이낸스 API 호출)
```bash
curl -X POST http://127.0.0.1:8123/run
```
- **기대**: 200 응답, `run_time`/`regime_bullish`/`recommendations` 필드 포함
- **실제 실행 결과** (2026-08-06T07:02:56Z 기준): `regime_bullish: false, recommendations: []` — 이 시점 BTC/ETH 4시간봉 구름대가 "위+양운" 조건을 만족하지 못해 하드필터가 정상 작동, 정상적인 케이스 (버그 아님)
- 서버 로그에 예외/재시도 경고 없음 — 업비트 후보군 조회, 캔들 수집, DB 저장까지 전 구간 정상 동작 확인

### 4. 저장된 결과 재조회
```bash
curl http://127.0.0.1:8123/recommendations
```
- **기대**: 3단계와 동일한 `run_time`의 결과 반환 (영속화 확인)
- **실제 결과**: 동일 `run_time`으로 정확히 재조회됨

### 5. 중복 실행 방지 확인 (선택, 수동)
`POST /run`을 짧은 간격으로 2번 연달아 호출 — 두 번째 호출이 아직 첫 번째가 끝나기 전이면 409 응답이어야 함 (개인 컴퓨터에서는 파이프라인이 수 초~수십 초 내 끝날 수 있어 타이밍 맞추기 어려울 수 있음 — 자동화 테스트(`test_pipeline.py::test_lock_prevents_concurrent_runs`)가 이 경로를 이미 결정적으로 검증함)

### Cleanup
```bash
# Ctrl+C로 서버 종료. data/coin_recommender.db는 실제 수집된 데이터라 유지해도 무방 (다음 실행이 증분 수집으로 이어짐)
```

## 알림 채널 검증 (선택, 수동 — 실제 텔레그램/디스코드 계정 필요)
`.env`에 `TELEGRAM_BOT_TOKEN`+`TELEGRAM_CHAT_ID` 또는 `DISCORD_WEBHOOK_URL`을 실제 값으로 채운 뒤 `POST /run` 실행 → 해당 채널에 메시지가 도착하는지 확인. 이 프로젝트 세션에서는 사용자의 실제 계정 정보가 없어 이 부분만 검증하지 못했습니다. `tests/test_notifier.py`가 메시지 포맷/채널 선택 로직은 커버합니다.
