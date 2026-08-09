# Business Rules — Unit 1: data-pipeline

## BR1. 후보군 필터
- KRW 마켓만 대상
- BTC, ETH 마켓 코드는 항상 제외
- 24시간 거래대금 기준 상위 20개만 후보로 선정

## BR2. 부트스트랩 최소 캔들 수
- 지표 계산용으로 최소 100봉 필요 (스팬B 52 + 선행이동 26 + 여유분 고려)
- 100봉 미만이면 해당 (market, timeframe)은 이번 회차에서 스킵 (신규 상장 등으로 이력 부족 시)

## BR3. 백테스트용 이력 수집
- `backtest_lookback_days` (기본 180일, `config/settings.yaml`에서 설정 가능) 만큼 추가 수집
- 지표용 100봉 수집과 동일한 upsert 대상 — 별도 로직/테이블 불필요

## BR4. 증분 수집 기준
- (source, market, timeframe)별 저장된 마지막 `candle_time` 이후 캔들만 조회
- 저장 이력이 없으면 BR2/BR3 적용 (부트스트랩)

## BR5. Upsert 유일성
- 유니크 키: (source, market, timeframe, candle_time)
- 동일 키로 재수집 시 값 갱신 (거래소가 진행 중 캔들을 보정하는 경우 대응)

## BR6. 타임스탬프 정규화
- 모든 `candle_time`은 UTC로 정규화해 저장 (업비트/바이낸스 소스 간 일관성 확보)

## BR7. 부분 실패 격리
- 특정 마켓의 수집이 실패(네트워크 오류, API 오류 등)해도 예외를 전체 파이프라인으로 전파하지 않고, 해당 마켓만 건너뛰고 나머지는 계속 처리 (RESILIENCY-10 graceful degradation)
- Binance BTC/ETH 수집 실패는 레짐 판정 자체가 불가능해지므로 Unit 2(Scorer)가 안전하게 빈 추천으로 처리 (Unit 1은 실패 사실만 전달)

## BR8. 바이낸스 후보군 필터 (신규 — 거래소별 추천 5개씩 요청, Requirements FR-B1)
- USDT 마켓만 대상 (기존 BTCUSDT/ETHUSDT 참조 종목과 동일한 견적통화 — 유동성/데이터 일관성)
- BTC, ETH(USDT) 마켓 코드는 항상 제외 (레짐 참고용으로만 사용, 추천 후보 아님 — BR1과 동일 원칙)
- **스테이블코인 페어 제외** (Requirements Q1): base 자산이 스테이블코인인 페어(예: USDCUSDT, FDUSDUSDT, TUSDUSDT, DAIUSDT, USDPUSDT 등)는 모멘텀 신호와 무관하므로 제외
- **레버리지/파생 토큰 제외** (Requirements Q1): base 심볼이 `UP`/`DOWN`/`BULL`/`BEAR`로 끝나는 페어(예: BTCUPUSDT) 제외
- 24시간 거래대금(quoteVolume) 기준 상위 20개만 후보로 선정 (BR1과 동일 개수, `top_n_candidates` 설정 재사용)

## BR9. 바이낸스 후보 코인 캔들 수집 (신규 — Requirements FR-B2)
- BR8로 선정된 각 바이낸스 후보 코인에 대해 1시간봉/4시간봉을 수집한다 (기존에는 BTC/ETH 4시간봉만 수집했음 — 1시간봉 골든크로스 시그널 계산에 필요하므로 신규 추가)
- 부트스트랩/증분/upsert/타임스탬프 정규화/부분 실패 격리 규칙은 BR2~BR7과 완전히 동일 (source="binance"로 동일한 `DataStore` 메서드 재사용, 신규 저장 로직 불필요)
