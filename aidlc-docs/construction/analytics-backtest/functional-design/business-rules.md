# Business Rules — Unit 2: analytics-backtest

## BR1. 일목균형표 계산식 (Code Generation 단계에서 pandas-ta 실측 후 정정됨)

캔들이 시간 오름차순으로 정렬되어 있고 인덱스 `i`가 0부터 시작한다고 할 때:

- `tenkan[i]` = (최근 9개 구간의 최고가 + 최저가) / 2
- `kijun[i]` = (최근 26개 구간의 최고가 + 최저가) / 2
- `senkou_a[i]` = (`tenkan[i-25]` + `kijun[i-25]`) / 2
- `senkou_b[i]` = (`i-25` 시점 기준 최근 52개 구간의 최고가 + 최저가) / 2

**정렬 규칙 (중요, 버그 유발 포인트 — 실측으로 확정)**: 애초 계획은 "26기간 시프트"였으나, 실제로 `pandas-ta`(0.4.71b0)의 `ichimoku()` 출력을 고정 시드 합성 데이터로 직접 검증한 결과, 스팬이 **25기간** 시프트되어 있음을 확인했습니다(대조 결과 오차 0). 텍스트북 정의(26)와 다르지만, `pandas-ta`를 그대로 사용하기로 했으므로(NFR Requirements 정정 사항) 라이브러리의 실측 동작을 그대로 채택합니다 — 어느 쪽이든 미래 데이터를 보지 않는 것(look-ahead 없음)이 핵심이며, 정확히 25 vs 26 자체는 임의적입니다. 프로덕션 코드는 `pandas-ta` 출력(`ISA_9`, `ISB_26`, `ITS_9`, `IKS_26`)을 추가 시프트 없이 그대로 사용합니다.

**워밍업 구간 (실측)**: `senkou_a`는 `i < 50`(= 9+26+25-... 실측상 인덱스 50부터 값 존재)까지 None, `senkou_b`는 `i < 76`까지 None. `kijun`은 `i < 25`까지 None. (정확한 경계는 pandas-ta 내부 rolling 구현에 따르며, 오라클 테스트가 이를 고정)

**후행스팬(Chikou)**: 계산하지 않음 (전략에서 미사용) — `pandas-ta`가 함께 반환하지만 우리 코드에서는 버림.

### 검증 방법

`tests/ichimoku_reference.py`에 순수 pandas rolling 기반 참조 구현(tenkan/kijun/senkou_b는 위 산식 그대로, senkou_a/b는 25기간 시프트)을 두고, `pandas-ta` 실제 출력과 오라클 테스트로 대조합니다 (Code Generation 단계에서 고정 시드 데이터로 실측 완료, 오차 0 확인됨).

## BR2. 구름 위/양운 판정 (레짐과 추세필터 공용)

- `above_cloud(i)` = `close[i] > max(senkou_a[i], senkou_b[i])`
- `bullish_cloud(i)` = `senkou_a[i] > senkou_b[i]`
- `is_bullish(i)` = `above_cloud(i) AND bullish_cloud(i)`

이 `is_bullish()` 함수는 4h 추세필터(BR3)와 BTC/ETH 레짐 판정(BR5) 양쪽에서 동일하게 재사용됩니다 (대상 데이터만 다름 — 알트코인 자체 4h vs BTC/ETH 4h).

## BR3. 4시간봉 추세 필터 (코인 자체)

`trend_pass(coin, t)` = 해당 코인의 4시간봉에서 `is_bullish(t)`가 True

## BR4. 1시간봉 골든크로스 — 이벤트 기반 (Q1=A)

`golden_cross_event(i)` = `tenkan[i-1] <= kijun[i-1] AND tenkan[i] > kijun[i]`

교차가 정확히 발생한 봉만 True. 이미 전환선이 기준선 위에 있는 봉들(상태 지속)은 포함하지 않음.

## BR5. BTC/ETH 레짐 판정 (Q3=A: AND 조합)

`regime_bullish(t)` = `is_bullish(BTC, t) AND is_bullish(ETH, t)`

## BR6. 복합 진입 시그널 (Application Design/Requirements의 "시그널 상태" 재정의)

`composite_signal(coin, i)` = `golden_cross_event(coin, i) AND trend_pass(coin, as_of_4h(i))`

여기서 `as_of_4h(i)`는 1시간봉 봉 `i`의 시각 기준으로, **그 시각 이전에 마감된 가장 최근 4시간봉**을 찾는 as-of 매칭입니다 (예: 1시간봉 13:00 봉은 4시간봉 12:00 봉을 참조 — 12:00~16:00 구간이 아직 진행 중이므로 가장 최근 마감분인 08:00~12:00 봉 사용).

## BR7. 라이브 추천 판정 순서

1. `regime_bullish(가장 최근 마감된 BTC/ETH 4h 봉)` 확인 — False면 즉시 빈 추천 리스트 반환 (FR8 하드 필터)
2. 각 후보 코인에 대해 `composite_signal(coin, 가장 최근 마감된 1h 봉)` 확인 — False면 해당 코인 스킵 (지금 시그널이 없음)
3. True인 코인만 Backtest로 기대수익률 조회 → 4% 이상만 최종 추천

## BR8. 백테스트 표본 수집 규칙

코인별로 저장된 전체 1시간봉 이력을 스캔하며, 각 봉 `i`에 대해:

1. `composite_signal(coin, i)`가 True인지 확인 (BR6)
2. **레짐 반영** (Q2=A): 그 시각의 `regime_bullish(as_of_4h(i))`가 True인 경우만 표본으로 채택
3. **최신성 제외**: 봉 `i` 시각이 "지금"으로부터 24시간 미만 전이면 제외 (24h 후 실제 수익률을 아직 관측 불가)
4. 위 조건을 모두 만족하면: `forward_return = (close[i+24] - close[i]) / close[i]` (1시간봉 24개 = 24시간)를 표본에 추가

집계:
- `n` = 표본 개수
- `expected_return` = 표본 평균 (표본 0개면 None)
- `hit_count` = 표본 중 `forward_return >= 0.04`인 개수

## BR9. N=0 처리 (Requirements에서 이미 확정, 재확인)

`expected_return`이 None이면(표본 0개) 해당 코인은 이번 회차 추천에서 제외.

## BR10. 추천 리스트 정렬

기대수익률(`expected_return`) 내림차순으로 정렬 (스펙에 명시되지 않았으나, 사용자가 결과를 볼 때 가장 유력한 추천부터 보는 것이 자연스러운 기본 동작 — 낮은 리스크의 기본값이라 별도 질문 없이 채택. 다른 정렬을 원하시면 Request Changes로 알려주세요)

## BR11. 추천 결과 사후 판별 (신규 — 추천 결과 적중 판별 및 학습 반영 요청, Requirements Q1/Q2)

**중요**: 이 규칙은 `expected_return`/`n`/`hit_count`(BR8) 계산 방식을 바꾸지 않습니다. BR8은 매 실행마다 코인의 전체 캔들 이력을 다시 스캔하므로, 캔들이 계속 쌓이면서 이미 자동으로 최신 실측 데이터를 반영합니다 (requirements.md "Code Investigation Findings" 참조). BR11은 별개로, **특정 추천 건(run_time, market)이 실제로 목표를 달성했는지 사후에 기록**하기 위한 규칙입니다.

- **entry_candle**: 그 추천의 `run_time` 시각 이하로 가장 최근에 마감된 코인의 1시간봉 (BR6의 as-of 매칭과 동일한 개념, 단 원본 캔들 사용 — Ichimoku 계산 불필요)
- **평가 구간(window)**: `entry_candle` 이후의 1시간봉 24개 (BR8의 forward window와 동일한 길이)
- **판별 불가**: `entry_candle`을 못 찾거나, window에 24개 미만의 캔들만 있으면(아직 데이터 부족) 판별 보류 — `target_reached`/`realized_return` 모두 미확정 상태 유지, 다음 회차에 재시도 (BR12)
- **target_reached** (Requirements Q1=B, 종가가 아닌 **구간 내 고가** 기준): window의 캔들 중 하나라도 `high >= entry_candle.close * 1.04`이면 True
- **realized_return** (BR8과 동일 산식 재사용, NFR-L1): `(window[-1].close - entry_candle.close) / entry_candle.close` — window 마지막(24번째) 봉의 종가 기준

`target_reached`는 BR8의 `hit_count`(과거 표본 중 몇 개가 기준을 넘었는지 세는 값)와 이름이 비슷하지만 다른 개념입니다 — `hit_count`는 회고적 백테스트 표본 집계, `target_reached`는 실제로 있었던 특정 추천 1건의 사후 결과입니다. 혼동 방지를 위해 필드명을 다르게 유지합니다.

## BR12. 판별 대상 선정 (신규)

- 대상: `run_time + 24시간 <= 지금`이고 아직 판별되지 않은(`evaluated_at IS NULL`) 추천 레코드 전부 (Requirements Q4 — 배포 이전 과거 기록 포함)
- 판별 가능한 만큼만 처리하고, BR11의 "판별 불가" 케이스는 조용히 스킵 (에러 아님) — 다음 회차에 다시 대상에 포함됨
- **알려진 한계 (Out of Scope, 별도 요청 없어 처리 안 함)**: 코인이 후보군에서 영구적으로 이탈해 더 이상 캔들이 안 쌓이면 해당 추천은 영원히 미판별 상태로 남을 수 있음 — 개인용 소규모 서비스 규모에서는 영향 미미하다고 판단해 타임아웃/포기 로직은 추가하지 않음

## BR13. 거래소별 추천 산출 (신규 — 거래소별 추천 5개씩 요청, Requirements FR-B3)

BR1~BR9(시그널 판정, 백테스트 표본 집계)는 완전히 거래소 무관(source-agnostic)하게 설계되어 있음 — `data_store.get_candles(source, market, timeframe)`만 소스별로 분기되고 나머지 계산 로직(`compute_ichimoku`, `golden_cross_event`, `compute_signal_stats` 등)은 그대로 재사용된다. 따라서 `generate_recommendations(candidates, source, data_store, now)`처럼 **source를 파라미터로 받아** 업비트 후보군과 바이낸스 후보군 각각에 대해 동일 함수를 호출하는 방식으로 확장한다 (신규 알고리즘 없음, FR-B7).

BTC/ETH 레짐 판정(BR5, `check_market_regime`)은 여전히 바이낸스 BTC/ETH 4시간봉 하나만 참조하는 전역 게이트로 유지한다 — 거래소별로 별도 레짐을 두지 않음(레짐은 "전체 시장 국면" 개념이라 소스 분리가 부적절, 기존 설계 그대로).

## BR14. 거래소별 상위 5개 결합 (신규 — Requirements FR-B4)

각 거래소에서 BR13으로 산출된 추천 리스트(이미 BR10에 따라 기대수익률 내림차순 정렬됨)를 각각 상위 `recommendations_per_exchange`개(기본 5, 설정값)까지만 자른 뒤 이어 붙인다.

- 업비트 상위 5개 + 바이낸스 상위 5개 = 최대 10개
- 한쪽 거래소에서 임계값(4%)을 통과한 코인이 5개 미만이면 있는 만큼만 포함 (Requirements Q2 — 미달분을 임계값 미만 코인으로 강제로 채우지 않음)
- 최종 리스트 내 정렬은 "업비트 그룹 먼저, 바이낸스 그룹 다음" 각각 기대수익률 내림차순 — 두 그룹을 다시 하나로 합쳐 재정렬하지 않음 (거래소별로 "5개씩 포함"되었음을 사용자가 리스트 형태로도 바로 알아볼 수 있도록, Requirements 취지 반영)
