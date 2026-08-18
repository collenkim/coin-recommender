# Business Rules — Unit 3: api-service

## BR1. 파이프라인 오케스트레이션 순서 (services.md 재확인)

1. `MarketSelector.get_candidate_markets()`
2. 후보/BTC/ETH 캔들 수집 및 저장 (Unit 1)
3. `Scorer.generate_recommendations()` (Unit 2) — 내부에서 레짐 하드필터 적용
4. 결과를 `pipeline_runs` + `recommendations` 테이블에 저장
5. `Notifier.send_notification()` 호출 (best-effort, 실패해도 파이프라인은 성공으로 간주)

## BR2. 동시 실행 방지

프로세스 내 락(예: `threading.Lock`)으로 파이프라인 중복 실행을 막는다. 이미 실행 중일 때 `POST /run`이 호출되면 파이프라인을 새로 시작하지 않고 "이미 실행 중" 응답(409)을 반환한다. 스케줄러 잡도 동일 락을 공유한다.

## BR3. 결과 저장은 항상 발생, 알림은 best-effort

파이프라인이 레짐 하드필터로 추천 0개를 반환하더라도 `pipeline_runs`에 실행 기록은 남긴다 (regime_bullish=False로). `Notifier` 전송이 실패(네트워크 오류 등)해도 예외를 상위로 전파하지 않고 로그만 남기며, 이미 저장된 결과는 그대로 유지된다.

## BR4. 알림 채널

`.env`에 `TELEGRAM_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL` 중 설정된 것마다 각각 발송. 하나만 설정되면 하나만, 둘 다 없으면 알림을 보내지 않고 로그만 남긴다 (에러 아님).

## BR5. 알림 메시지 형식

```
[coin-recommender] {run_time} 추천 결과

- {market}: 기대수익률 {expected_return:.1%} (과거 {n}회 중 {hit_count}회 적중)
- ...

(추천 없음이면: "이번 회차 추천 없음")
```

## BR6. GET /recommendations 응답

`pipeline_runs`에서 가장 최근 `run_time`을 조회 → 해당 `run_time`의 `recommendations` 행 전체 반환. 아직 한 번도 실행되지 않았으면 (`pipeline_runs`가 비어있으면) 빈 결과 + `run_time: null`을 반환 (에러 아님, 정상적인 초기 상태).

## BR7. GET /health

DB 연결을 확인하는 간단한 쿼리(`SELECT 1`)를 실행해 성공하면 `{"status": "ok", "db_connected": true}`, 실패하면 500과 함께 `{"status": "error", "db_connected": false}` 반환 (RESILIENCY-06).

## BR8. POST /run 동기/비동기

`POST /run`은 파이프라인 실행이 끝날 때까지 기다렸다가(동기) 결과를 반환한다 (스펙에 "수동 트리거"라고만 되어 있고 별도 비동기 요구가 없으므로 가장 단순한 방식 채택 — 매시 실행이 몇 분 내 끝나는 규모라 응답 지연이 크지 않음).

## BR9. 추천 결과 판별 배치 (신규 — Requirements Q3/Q4)

- `run_recommendation_pipeline()` 본연의 흐름(BR1) 끝에서, 판별 대상(Unit 2 BR12) 추천 건들을 모두 조회해 `Backtest.evaluate_outcome()`(Unit 2 BR11)을 호출하고 결과를 저장한다.
- 같은 락(BR2) 안에서 실행 — 스케줄러/`POST /run` 어느 쪽으로 트리거되든 동일하게 처리되고, 파이프라인과 동시 실행되지 않음.
- 개별 추천 건의 판별 실패(데이터 부족 등)는 로그만 남기고 나머지 건은 계속 처리한다 (BR7의 부분 실패 격리 패턴 재사용).
- 배포 이전 과거 추천 기록도 이 배치의 판별 대상에 자연히 포함된다 (Unit 2 BR12가 `evaluated_at IS NULL`인 모든 건을 대상으로 하므로 별도 백필 스크립트 불필요).

## BR10. GET /recommendations 확장 응답 (신규 — Requirements Q5, FR-L5)

- 쿼리 파라미터 `limit` (기본값 1).
- `limit=1`(기본, 파라미터 생략 포함)일 때: 응답의 최상위 구조(`run_time`, `regime_bullish`, `recommendations`)는 기존과 100% 동일하게 유지 (하위 호환) — 단, 각 `recommendations` 항목에 `target_reached`(bool | null)와 `realized_return`(float | null) 필드가 추가된다 (미판별이면 둘 다 null). 기존 클라이언트는 모르는 필드를 무시하므로 영향 없음.
- `limit>1`일 때: 위 최상위 필드는 그대로 최신 회차를 나타내고, 추가로 `history` 필드에 최근 `limit`개 회차(최신 포함, `run_time` 내림차순)를 같은 모양(`run_time`/`regime_bullish`/`recommendations`)의 리스트로 담아 반환한다. 저장된 회차가 `limit`보다 적으면 있는 만큼만 반환 (에러 아님).

## BR11. 거래소 구분 노출 (신규 — 거래소별 추천 5개씩 요청, Requirements FR-B5/FR-B6)

- `POST /run`, `GET /recommendations` 응답의 각 추천 항목에 `source`("upbit" | "binance") 필드를 추가한다.
- 알림 메시지(BR5)의 각 항목 앞에 거래소 구분을 표시한다: `- [{source}] {market}: 기대수익률 ...` (예: `- [upbit] KRW-XRP: ...`, `- [binance] SOLUSDT: ...`).
- `MarketSelector`/`Pipeline`이 이미 업비트 그룹 5개 + 바이낸스 그룹 5개 순서로 리스트를 구성해 넘기므로(Unit 2 BR14), API/알림은 받은 순서를 그대로 노출하기만 하면 된다 — 별도 재정렬/그룹핑 로직 불필요.

## BR12. 진입 가이드 노출 (신규 — 2026-08-10, Requirements FR-G2)

`GET /recommendations`와 `POST /run`의 각 추천 항목에 Unit 2 BR16의 진입 가이드를 포함한다:
`entry_time`, `entry_price`, `target_price`, `exit_deadline`, `max_drawdown`.

- `target_price`(진입가×1.04)와 `exit_deadline`(진입+24시간)은 **응답 시점에 파생 계산**하고 DB에 저장하지 않는다 — 저장하면 규칙 변경 시 값이 어긋난다.
- DB에는 `entry_time`, `entry_price`, `max_drawdown` 3개 컬럼만 추가한다(기존 ALTER TABLE 마이그레이션 방식 재사용, 기존 행은 NULL).
- 진입 정보가 없는 과거 행(이 기능 이전 데이터)은 해당 필드가 모두 `null`로 나가고, 알림에서는 가이드 줄 자체를 생략한다 — 없는 값을 만들어내지 않는다.
- 알림 메시지 형식:
```
- [binance] TUTUSDT: 기대수익률 0.4% (과거 21회 중 4회 적중)
    진입 0.2294 (08-10 04:00 UTC 종가 기준) → 목표 0.2386 (+4%)
    청산 기한 08-11 04:00 UTC (진입 +24시간)
    과거 동일 신호 최대 낙폭 -17.3% (손절 지시 아님, 참고용)
```

## BR13. 추천 유효기간 24시간 (신규 — 2026-08-10, Requirements FR-G3)

서비스가 예측하는 것은 **하루 안의 움직임**이므로, 추천은 진입 시점으로부터 24시간(백테스트 측정 구간과 동일)이 지나면 실행 대상이 아니다.

- `GET /recommendations`의 최신 회차가 `run_time + 24시간`을 넘겼으면 `recommendations`를 **빈 배열**로 반환하고 `expired: true`를 함께 준다. `run_time`은 그대로 유지해 "실행된 적 없음"(`run_time: null`)과 구분한다.
- 판정 기준으로 개별 `entry_time`이 아니라 회차의 `run_time`을 쓴다 — 한 회차의 모든 추천은 같은 시각대에 생성되므로 결과가 같고, 진입 정보가 없는 과거 행도 함께 처리된다.
- `history`(limit>1)는 만료와 무관하게 그대로 반환한다 — 실행 기록 조회 목적이지 실행 대상이 아니기 때문.
- `POST /run`은 방금 실행한 결과이므로 만료 판정을 적용하지 않는다.

**이 규칙이 실제로 필요한 이유**: 파이프라인은 매시 목록을 갱신하므로 정상 운영 중에는 만료가 발생하지 않는다. 그러나 스케줄러/컨테이너가 멈추면 `get_latest_run()`이 며칠 전 회차를 **현재 추천처럼** 반환하며, 하루 지난 진입가로 진입을 유도하게 된다. 만료 처리는 그 상황에 대한 안전장치다.

## BR22. 가격 도달 감시 스케줄러 (2026-08-11)

추천이 나온 뒤 24시간 동안 5분마다 진입가/매도가/손절가 도달을 확인하고, 도달 시 알림을 보냅니다.

**판정 기준**:
- **진입가 도달** = 추천 이후 저가가 진입가 이하로 내려온 시점. 추천 시점의 진입가는 그 순간의 종가라 이미 도달 상태이므로, "다시 진입가까지 내려와 지금 진입 가능해진 시점"으로 해석합니다.
- **매도가 도달** = 고가 >= 진입가 x 1.03
- **손절가 도달** = 저가 <= 진입가 x 0.98
- 한 봉에서 매도가와 손절가를 동시에 만족하면 `simulate_trade`(BR18)와 동일하게 **손절 우선**으로 봅니다.
- 매도가 또는 손절가에 닿으면 포지션이 끝난 것이므로 해당 종목 감시를 종료합니다.

**1분봉을 쓰는 이유**: 5분 간격의 시점 가격만 보면 그 사이에 스쳐간 도달을 놓칩니다. 백테스트가 고가/저가로 터치를 판정하므로 감시도 같은 기준이어야 합니다. `get_klines_since(symbol, "1m", entry_time)`으로 진입 이후 전체를 매번 다시 훑습니다 -- 별도의 "마지막 확인 시각" 상태를 두지 않아도 컨테이너 다운타임 중 발생한 도달을 놓치지 않습니다. 활성 추천 5건 기준 5분마다 최대 10요청(시간당 120요청)으로 Binance 레이트리밋 대비 여유가 큽니다.

**중복 방지**: `entry_touched_at` / `target_hit_at` / `stop_hit_at` 컬럼에 최초 도달 시각을 기록하고, `mark_price_event`는 NULL일 때만 UPDATE합니다. 기록 자체가 "이미 알렸다"는 표시이므로 별도 플래그가 없습니다. 이벤트가 없으면 알림을 보내지 않습니다 -- 5분마다 "변화 없음"을 보내면 하루 288통이 됩니다.

**스케줄**: `CronTrigger(minute="*/5")`, 파이프라인(매시 :05)과 별도 잡. 파이프라인 락을 공유하지 않습니다 -- 읽기 위주에 짧은 UPDATE만 하고, 시간당 1회 파이프라인이 도는 동안에도 감시는 계속되어야 합니다(SQLite WAL).

**발견한 결함 (같은 작업 중 수정)**: `TIMEFRAME_HOURS`에 `1m`이 없어 `drop_unclosed`가 KeyError를 냈고, 감시 루프의 예외 처리에 먹혀 **이벤트 0건으로 조용히 넘어갔습니다.** 목 클라이언트 단위 테스트로는 잡히지 않고 실제 거래소 호출에서만 드러난 종류입니다. 회귀 방지 테스트를 `test_data_store.py`에 추가했습니다.

## BR23. 시장 국면 문구 노출 (2026-08-18)

판정 규칙 자체는 Unit 2의 BR23을 따른다. 여기서는 **표시 방식**만 정한다.

### 알림 문구 (`notifier._format_message`)

헤드라인 한 줄 + 자산별 한 줄:

```
[coin-recommender] 추천 코인 0개
2026-08-18 09:20 KST

상승장 아님 — BTC·ETH가 함께 상승하고 있지는 않습니다
· BTCUSDT 비상승:  일 +2.6%  주 +0.9%  30일 -0.5%  월 -16.0%  년 -45.0%
· ETHUSDT 약상승:  일 +2.0%  주 +2.2%  30일 +2.7%  월 -9.4%  년 -57.2%

이번 회차 추천 없음
```

헤드라인 3종:
- 강상승장 — BTC·ETH 둘 다 상승 모멘텀이 강합니다
- 약상승장 — BTC·ETH 둘 다 상승 중이지만 강세까지는 아닙니다
- 상승장 아님 — BTC·ETH가 함께 상승하고 있지는 않습니다

문안에 "오른다"는 뜻이 읽히는 표현을 쓰지 않는다 — Unit 2 BR23대로 예측력을 주장할 근거가 없다.

### 추천 0건일 때도 넣는다

이 줄이 없으면 `"이번 회차 추천 없음"`이 **게이트가 닫혀서 0건인지, 열렸는데 통과한 코인이 없어서 0건인지** 구분되지 않는다 (2026-08-13 진단에서 기록된 문제). 그래서 추천 유무와 무관하게 항상 넣는다.

### 판정 불가 시 생략

이력이 모자라 판정할 수 없으면 **줄을 통째로 뺀다**. 모르는 것을 "상승장 아님"으로 적으면 데이터 결손이 시장 판단으로 둔갑한다. 한 자산만 판정 가능하면 그 자산만으로 판정한다(문구가 통째로 사라지는 것보다 낫다).

### API 노출 (`GET /recommendations`, `POST /run`)

최상위에 `market_phase`를 추가한다 (`phase`, `assets[].market/label/returns`).

- **저장하지 않고 조회 시점에 계산한다** — 국면은 회차의 속성이 아니라 현재 시장의 속성이다. DB 스키마는 건드리지 않는다.
- **`history`의 과거 회차에는 붙이지 않는다** — 붙이면 지난 회차가 그때의 국면이었던 것처럼 읽힌다.
- 기존 `regime_bullish`(진입 게이트)와는 **별개 기준이라 둘이 어긋날 수 있다.** 게이트는 BTC 30일 단독, 국면은 BTC/ETH 5구간이다.
