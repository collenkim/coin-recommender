# Units of Work — coin-recommender

## Unit 1: data-pipeline
- **책임**: 후보군 선정, 업비트/바이낸스 캔들 수집(부트스트랩+증분), SQLite 저장
- **컴포넌트**: MarketSelector, UpbitClient, BinanceClient, DataStore
- **빌드 순서**: 1번째 (사용자 요청: "데이터 수집 → 저장" 순서 반영)

## Unit 2: analytics-backtest
- **책임**: 일목균형표 계산, 시그널 상태별 과거 수익률 통계, 기대수익률 기반 추천 스코어링
- **컴포넌트**: Features, Backtest, Scorer
- **빌드 순서**: 2번째 (사용자 요청: "일목균형표 계산" 이후 단계)

## Unit 3: api-service
- **책임**: 파이프라인 오케스트레이션, 스케줄링, 알림, REST API 노출
- **컴포넌트**: Pipeline, Scheduler, Notifier, API
- **빌드 순서**: 3번째 (Unit 1/2를 조합하는 최종 조립 단계)

## Code Organization Strategy (Greenfield)

원래 요청된 평면(flat) `src/` 구조를 그대로 유지합니다. 유닛은 물리적 디렉토리 분리가 아니라 **Construction 단계의 설계+구현+검증 체크포인트** 단위입니다.

```
coin-recommender/
├── config/
│   └── settings.yaml
├── .env                      # 시크릿 (웹훅 URL 등), 커밋 제외
├── src/
│   ├── upbit_client.py       # Unit 1
│   ├── binance_client.py     # Unit 1
│   ├── market_selector.py    # Unit 1
│   ├── data_store.py         # Unit 1
│   ├── features.py           # Unit 2
│   ├── backtest.py           # Unit 2
│   ├── scorer.py             # Unit 2
│   ├── pipeline.py           # Unit 3
│   ├── notifier.py           # Unit 3
│   ├── scheduler.py          # Unit 3
│   └── api.py                # Unit 3
├── tests/
└── requirements.txt
```
