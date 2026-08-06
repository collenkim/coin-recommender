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
