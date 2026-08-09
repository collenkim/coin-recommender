# Domain Entities — Unit 2: analytics-backtest

## IchimokuPoint
캔들 1개에 대응하는 일목균형표 지표 값 (거래소/코인 무관, 순수 계산 결과)

| Field | Type | 설명 |
|---|---|---|
| candle_time | datetime (UTC) | 대응 캔들 시각 |
| tenkan | float \| None | 전환선 (워밍업 구간은 None) |
| kijun | float \| None | 기준선 |
| senkou_a | float \| None | 선행스팬A — **이 바(bar)에 적용되는** 구름 경계값 (미래 투영 없이 정렬됨, business-rules.md 참조) |
| senkou_b | float \| None | 선행스팬B — 위와 동일 |
| close | float | 원본 종가 (구름 위/아래 판정에 사용) |

후행스팬(Chikou)은 계산하지 않음 (전략에서 사용하지 않음, functional-design-plan.md에 근거 명시).

## RegimeStatus
특정 4시간봉 시점의 BTC/ETH 종합 레짐 판정

| Field | Type | 설명 |
|---|---|---|
| candle_time | datetime (UTC) | 4시간봉 시각 |
| btc_bullish | bool | BTC가 "구름 위 + 양운"인지 |
| eth_bullish | bool | ETH가 "구름 위 + 양운"인지 |
| regime_bullish | bool | `btc_bullish AND eth_bullish` (Q3=A) |

## SignalStats
백테스트 결과 통계

| Field | Type | 설명 |
|---|---|---|
| market | str | 대상 마켓 |
| expected_return | float \| None | 과거 표본 평균 24h 수익률, 표본 없으면 None |
| n | int | 표본 수 |
| hit_count | int | 표본 중 24h 수익률이 +4% 이상이었던 횟수 |

## Recommendation
최종 추천 항목

| Field | Type | 설명 |
|---|---|---|
| market | str | 마켓 코드 |
| source | "upbit" \| "binance" | 신규 (BR13) — 추천이 산출된 거래소 |
| expected_return | float | 기대수익률 (>= 0.04) |
| n | int | 표본 수 |
| hit_count | int | 적중 횟수 |

## RecommendationOutcome (신규 — BR11)
특정 추천 건(run_time, market)의 사후 판별 결과

| Field | Type | 설명 |
|---|---|---|
| market | str | 마켓 코드 |
| run_time | datetime (UTC) | 대상 추천의 실행 시각 (Unit 3의 `recommendations` 레코드 참조) |
| target_reached | bool | 평가 구간(24시간) 내 고가 기준 목표수익률(4%) 도달 여부 (BR11) |
| realized_return | float | 평가 구간 마지막 봉 종가 기준 실제 수익률 (BR11, BR8과 동일 산식) |
| evaluated_at | datetime (UTC) | 판별이 수행된 시각 |

판별 불가(데이터 부족)일 때는 이 엔티티 자체를 만들지 않음 — `None` 반환으로 "아직 판별 못함"을 표현 (BR11).
