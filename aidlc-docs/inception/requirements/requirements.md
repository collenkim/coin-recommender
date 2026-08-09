# Requirements — 바이낸스/업비트 거래소별 추천 5개씩 포함

## Intent Analysis Summary
- **User Request**: "Using AI-DLC 추천 리스트를 바이낸스, 업비트 기준 각각 5개씩 포함될 수 있도록 추가해주고, 바이낸스 거래량 최상위 20개로 추천 5개 찾아줘."
- **Request Type**: Enhancement / New Feature — Unit 1(data-pipeline), Unit 2(analytics-backtest), Unit 3(api-service) 모두에 걸침
- **Scope Estimate**: Multiple Components
- **Complexity Estimate**: Complex — 신규 후보 소스 추가, 신규 데이터 수집 경로, 추천 결합 로직 변경, DB 스키마 변경
- **Depth Applied**: Standard

## Code Investigation Findings
- 현재 추천 후보는 **업비트 KRW 마켓 거래대금 상위 20개**(`MarketSelector`, BTC/ETH 제외)에서만 산출된다. 바이낸스는 오직 BTC/ETH 4시간봉을 "시장 레짐(regime) 필터" 참고용으로만 사용하고, 바이낸스 자체 코인은 추천 후보가 된 적이 없다.
- 바이낸스에서는 4시간봉만 수집한다(BTC/ETH regime 용). 1시간봉 골든크로스 시그널 계산에 필요한 바이낸스 1시간봉은 전혀 수집되지 않는다.
- `src/data_store.py`는 이미 `Source = Literal["upbit", "binance"]`로 소스별 캔들 테이블이 분리되어 있어, 바이낸스 코인에 대해서도 기존 `compute_ichimoku`/`golden_cross_event`/`compute_signal_stats` 로직을 그대로 재사용할 수 있다(신규 알고리즘 불필요).
- `recommendations` 테이블/`Recommendation`/`RecommendationRecord`에는 거래소 구분 컬럼이 없다 — 마켓 심볼 형식이 달라(`KRW-XXX` vs `XXXUSDT`) 문자열 충돌은 없지만, API/알림에서 거래소를 명시적으로 표시하려면 신규 컬럼이 필요하다.

## Clarifying Answers (AskUserQuestion, 대화 중 확인)
| # | Question | Answer |
|---|---|---|
| 1 | 바이낸스 상위 20개 후보 산정 시 스테이블코인/레버리지 페어 제외 여부 | 제외한다 — 모멘텀 신호와 무관한 페어(USDCUSDT, FDUSDUSDT 등 스테이블, UPUSDT 등 레버리지 토큰)를 후보에서 걸러내고 실질 코인만 상위 20개로 집계 |
| 2 | 거래소별 신호 통과 코인이 5개 미만일 때 처리 | 있는 만큼만 포함 — 기존 기대수익률 4% 임계값(BR7)을 유지, 미달 시 강제로 채우지 않음 (0~5개 가변) |

## Functional Requirements
- FR-B1: 바이낸스에서도 업비트와 동일한 방식으로 "거래대금 상위 20개 후보"를 산출한다 — 대상은 USDT 마켓, BTC/ETH(레짐 참고용) 제외, 스테이블코인 페어 및 레버리지 토큰 페어 제외(Q1).
- FR-B2: 바이낸스 후보 코인에 대해 1시간봉/4시간봉을 업비트 후보와 동일한 방식(부트스트랩/증분)으로 수집·저장한다.
- FR-B3: 바이낸스 후보 코인에 대해 기존과 동일한 시그널(골든크로스 + 4시간봉 구름대 추세 + 레짐 필터 + 기대수익률 4% 임계값)로 추천 여부를 판정한다 — 판정 로직 자체는 거래소와 무관하게 재사용(신규 알고리즘 없음).
- FR-B4: 최종 추천 리스트는 업비트 상위 5개(기대수익률 내림차순) + 바이낸스 상위 5개(기대수익률 내림차순)로 구성한다. 각 거래소에서 임계값을 통과한 코인이 5개 미만이면 있는 만큼만 포함한다(Q2) — 총 0~10개.
- FR-B5: 각 추천 항목에 거래소 구분(`source`: "upbit" | "binance")을 추가해 저장·조회·알림 모두에 노출한다.
- FR-B6: `GET /recommendations`, `POST /run` 응답 및 텔레그램/디스코드 알림 메시지에 거래소 구분을 표시한다.
- FR-B7 (명시적 비범위): 시그널 계산 알고리즘(golden cross, ichimoku, 기대수익률 계산) 자체는 변경하지 않는다 — 기존 로직을 소스만 다르게 하여 재사용.

## Non-Functional Requirements
- NFR-B1 (Consistency): 바이낸스 후보 선정/캔들 수집은 기존 업비트 파이프라인과 동일한 장애 격리 원칙(RESILIENCY-10, 개별 마켓 실패가 다른 마켓에 영향 없음)을 따른다.
- NFR-B2 (Schema Evolution): 이미 배포된 DB(`recommendations` 테이블에 기존 데이터 존재)에도 안전한 마이그레이션(컬럼 추가, 기존 행은 `source='upbit'`로 채움)을 사용한다 — 과거 데이터는 전부 업비트 추천이었으므로 이 기본값이 사실과 일치한다.
- NFR-B3 (Rate/Load): 바이낸스 후보 20개 추가로 인한 API 호출 증가가 기존 재시도/백오프/타임아웃 정책(이미 구현됨) 안에서 처리되어야 한다 — 새 정책 불필요.

## Out of Scope
- 바이낸스 실주문/인증 연동 (여전히 공개 API만 사용).
- 거래소별 상위 20개 후보 개수 자체를 설정 가능하게 만드는 것(기존 `top_n_candidates=20`을 양쪽에 재사용, 신규 설정 불필요) — 단, "거래소별 최종 추천 개수(5개)"는 향후 조정 가능하도록 별도 설정값(`recommendations_per_exchange`, 기본 5)으로 둔다.
