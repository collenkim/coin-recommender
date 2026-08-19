# AI-DLC State Tracking

## Project Information
- **Project Name**: coin-recommender
- **Project Type**: Greenfield
- **Start Date**: 2026-08-06T00:00:00Z
- **Current Stage**: COMPLETE (Operations is a placeholder, no further stages defined)

## Execution Plan Summary
- **Total Stages**: Application Design, Units Generation, 3x per-unit (Functional Design, NFR Requirements, NFR Design, Code Generation), Build and Test
- **Stages to Execute**: Application Design, Units Generation, Functional Design (per unit), NFR Requirements (per unit), NFR Design (per unit), Code Generation (per unit, always), Build and Test (always)
- **Stages to Skip**: User Stories (single personal user, no persona complexity), Infrastructure Design (no cloud infra, local single instance) — **superseded 2026-08-07**: user requested Docker Compose infra for always-on VM deployment; Infrastructure Design executed for that follow-up request (see below)
- **Units of Work**: 1) data-pipeline (upbit_client, binance_client, market_selector, data_store) 2) analytics-backtest (features, backtest, scorer) 3) api-service (api, scheduler, notifier)

## Workspace State
- **Existing Code**: No
- **Reverse Engineering Needed**: No
- **Workspace Root**: C:\Users\김우석(카이)\IdeaProjects\coin-recommend

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration
| Extension | Enabled | Scope | Decided At |
|---|---|---|---|
| Security Baseline | Yes | Full, except SECURITY-08 (auth) marked N/A — local personal use, not externally exposed | Requirements Analysis |
| Resiliency Baseline | Yes | Code-level only (RESILIENCY-06 health check, RESILIENCY-10 timeouts/retry/graceful degradation, RESILIENCY-05 basic logging). Cloud/production items (DR, multi-region, change mgmt, CI/CD, chaos testing, incident response) marked N/A — local single instance, no cloud deployment | Requirements Analysis |
| Property-Based Testing | Yes | Partial — PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 enforced (blocking); others advisory | Requirements Analysis |

## Stage Progress

### 🔵 INCEPTION PHASE
- [x] Workspace Detection
- [x] Requirements Analysis
- [x] User Stories (SKIPPED — approved by user)
- [x] Workflow Planning
- [x] Application Design
- [x] Units Generation

### 🟢 CONSTRUCTION PHASE
- [x] Unit 1 (data-pipeline): Functional Design, NFR Requirements, NFR Design, Code Generation
- [x] Unit 2 (analytics-backtest): Functional Design, NFR Requirements, NFR Design, Code Generation
- [x] Unit 3 (api-service): Functional Design, NFR Requirements, NFR Design, Code Generation
- [x] Build and Test

### 🟡 OPERATIONS PHASE
- [ ] Operations (placeholder)

### 🔁 Follow-up Request (2026-08-07): Docker Compose Infrastructure
- [x] Requirements Analysis (Minimal/Standard depth — see `aidlc-docs/inception/requirements/requirements.md`)
- [x] Infrastructure Design (see `aidlc-docs/construction/infrastructure-design/infrastructure-design.md`)
- [x] Code Generation — `Dockerfile`, `.dockerignore`, `docker-compose.yml`, README docker section
- [x] Verified live: `docker compose build` → `up` → container reported `(healthy)` → `GET /health` and `GET /recommendations` returned real data from the bind-mounted `./data` DB → `docker compose down`

### 🔁 Follow-up Request (2026-08-07): 추천 결과 적중 판별 및 학습 반영
- [x] Requirements Analysis (Standard/Comprehensive — see `aidlc-docs/inception/requirements/requirements.md`, overwritten from the docker request's version; key finding: the "학습" effect already happens automatically via compute_signal_stats' full re-scan, scope narrowed to outcome recording/tracking)
- [x] Functional Design — Unit 2 analytics-backtest (BR11/BR12, RecommendationOutcome) + Unit 3 api-service (BR9/BR10, schema migration, GET /recommendations?limit=)  — Unit 1 data-pipeline skipped (no business-logic changes)
- [x] NFR Requirements/NFR Design — skipped (reuses existing stack, no new infra/tech-stack decisions)
- [x] Code Generation — src/backtest.py, src/data_store.py, src/pipeline.py, src/api.py + 15 new tests (91/91 passing)
- [x] Verified live against the real pre-existing `data/coin_recommender.db` (predates this feature): migration confirmed via PRAGMA table_info before/after, real server boot + GET /health, GET /recommendations, GET /recommendations?limit=3 all correct and backward-compatible

### 🔁 Follow-up Request (2026-08-10): 바이낸스/업비트 거래소별 추천 5개씩 포함
- [x] Requirements Analysis (Standard depth — see `aidlc-docs/inception/requirements/requirements.md`, overwritten from the outcome-tracking request's version; 2 clarifying questions resolved via AskUserQuestion: exclude stablecoin/leveraged Binance pairs, no forced-fill below 5)
- [x] Functional Design — Unit 1 data-pipeline (BR8 Binance top-20 filter, BR9 1h+4h candle collection), Unit 2 analytics-backtest (BR13 source-parameterized `generate_recommendations`, BR14 per-exchange top-5 cap+concat), Unit 3 api-service (BR11 `source` exposure + DB migration)
- [x] Code Generation — src/data_store.py (TickerInfo moved here, source column+migration), src/upbit_client.py, src/binance_client.py (get_tickers_by_volume), src/market_selector.py (BinanceMarketSelector), src/scorer.py, src/pipeline.py, src/notifier.py, src/api.py, src/config.py, config/settings.yaml + 7 test files updated/extended. Full suite: 106/106 passing (up from 91)
- [x] Verified live against the real pre-existing `data/coin_recommender.db` (backed up first): migration confirmed additive via PRAGMA table_info, GET /health + GET /recommendations correct post-migration, then a real POST /run against live Upbit/Binance APIs selected exactly 20 filtered Binance candidates, bootstrapped their 1h+4h candles with no errors, and completed successfully (regime_bullish=true, 0 recommendations this run — legitimate, no coin cleared the 4% threshold at test time)

### 🔁 Follow-up Request (2026-08-10): 추천 발생 빈도 개선 (골든크로스 유효 구간 완화)
- [x] 진단 — "추천이 계속 없다"는 지적을 실측 조사. 레짐 게이트는 정상 통과 중이었고(사용자 지적이 맞음), 서비스/데이터 수집도 정상. 진짜 병목은 BR4의 "정확히 최신 봉 골든크로스"로, 30일 시뮬레이션상 평균 103시간에 1회(독립 기회 7건)만 발생
- [x] Requirements Analysis — 사용자의 1차 선택(임계값 인하)을 실측 근거로 반박 후 재확인. 임계값은 4%→3%가 무변화, 0%까지 없애도 천장이 28시간 간격인 반면 적중률만 81%→40%로 하락. 최종 결정: **골든크로스 3봉 확대 + 임계값 4% 유지**
- [x] Code Generation — `golden_cross_within()` 신설, 백테스트(`_composite_signal`)와 라이브(`_composite_signal_on_latest_bar`) 양쪽을 동일 기준으로 전환. 테스트 7개 추가/1개 재작성, 113/113 통과
- [x] Verified live: 골든크로스 통과 코인 0 → 3개로 실제 변화 확인(이후 품질 필터에서 정상 기각), 도커 재빌드 후 컨테이너 healthy + 엔드포인트 정상
- [x] ~~미해결 한계: 표본 중복으로 `n` 부풀려짐~~ → 아래 신뢰도 개선 요청에서 해결됨

### 🔁 Follow-up Request (2026-08-10): 추천 신뢰도 향상 (버그 2건 + 근거 하한)
- [x] 질문 답변 — (1) 표본 증가는 순수 중복이 맞음(표본 78→238이지만 실제 교차는 78→83, +6%). (2) 4% vs 3%는 표본 차이가 아니라 분포 공백(4.69% 다음이 2.77%, 3~4% 구간에 코인 0개)
- [x] 조사 중 결함 2건 발견 — ① 중복 표본이 기대수익률 값 자체를 왜곡(KRW-ONDO -0.88%→+2.32% 부호 반전) ② 바이낸스 이력이 설정의 1/4.5만 수집(Binance 1,000개 응답 상한에서 조용히 잘림, 페이지네이션 부재)
- [x] Requirements Analysis — 버그 2건 수정 + 최소 교차 3회, 바이낸스 이력 180일로 업비트와 통일
- [x] Code Generation — `get_klines_since()` 페이지네이션, `get_first_candle_time()` 기반 백필, 교차 단위 표본 dedup(`_last_cross_bar`), `MIN_SIGNAL_SAMPLES=3` 근거 하한. 바이낸스 수집 함수 2개를 1개로 통합(동일 수정이 양쪽에 필요했으므로). 테스트 123/123 통과
- [x] Verified live: 운영 DB 사본에서 먼저 검증(1,007봉→4,320봉, 재실행 시 증분 전환 확인) 후 실제 배포. 바이낸스 평균 교차수 3.5→7.5회, 자격 코인 4→2개이며 탈락한 ZECUSDT(+5.16%→-0.67%)·KRW-WLD(교차 1회)는 짧은 이력이 만든 거짓 양성

### 🔁 Follow-up Request (2026-08-10): 진입 가이드 및 24시간 유효기간
- [x] 조사 — ① 유효기간 없음(스케줄러 정지 시 며칠 전 추천이 현재 추천처럼 반환) ② 진입 정보 전무 ③ **버그 발견**: 미완성(진행 중) 봉으로 시그널 판정. BR7의 "마감된 봉" 규정 및 scheduler.py의 ":05에 봉 마감 대기" 의도와 모두 모순
- [x] Requirements Analysis — 만료 시 목록 비우고 `expired` 표시, 가이드 4항목. 손절가는 표본 184건 실측 후 기각(승자/패자 낙폭 분포가 겹쳐 구분력 없음, -2% 손절 시 승자의 47% 손실) → 낙폭 통계로 대체
- [x] Code Generation — `drop_unclosed()`로 미완성 봉 제외(수집 단계), 진입 시각/가격/목표가/청산기한/낙폭, `expired` 만료 처리. 목표가·청산기한은 저장 대신 파생 계산. 테스트 136/136 통과
- [x] Verified live: 거래소 실호출로 미완성 봉 제외 확인(07:16 기준 최신 1h=06:00, 4h=00:00 모두 마감분). 현재 시그널이 없어, 실제 시그널이 있었던 과거 시점(2026-08-10T04:00Z, binance/TUTUSDT)으로 되감아 실전 코드 경로 통과 검증 — 진입 0.22939 @ 04:00 봉 마감, 목표 0.238566, 청산기한 +24h, 낙폭 -17.33%. 운영 DB 마이그레이션 3개 컬럼 확인
- [ ] **문서화된 주의사항**: `expected_return`은 손절 없이 24시간 보유 기준 값 — 사용자가 임의 손절을 걸면 이 숫자와 달라짐

### 🔁 Follow-up Request (2026-08-11): 백테스트 이력 1년(365일) 확대
- [x] 조사 — 사용자 질문("1년치 저장하는거지?")에 대한 답: **저장한다**(SQLite `data/coin_recommender.db`, 이력이 충분한 마켓은 실행당 타임프레임당 1건의 증분 요청만). 단 **설정값만 365로 바꾸면 업비트에는 적용되지 않음**을 발견 — `_collect_and_store`가 부트스트랩을 "DB가 비었는가"로만 판정해 기존 마켓은 증분(전진 전용) 경로에 갇힘. 바이낸스는 BR10 백필이 이미 있어 자동 확대
- [x] Requirements Analysis (Minimal depth — FR-Y1~FR-Y3, `aidlc-docs/inception/requirements/requirements.md`에 추가)
- [x] Functional Design — Unit 1 data-pipeline BR11 신설(업비트 소급 백필), BR3/BR4 갱신. Unit 2는 설정값 확대 효과만 받으므로 설계 변경 없음
- [x] Code Generation — `config/settings.yaml`+`src/config.py` 180→365, `src/pipeline.py` `_bars_between()`/업비트 백필 분기, `src/binance_client.py` 폭주 상한 주석 갱신. 테스트 3개 추가, 139/139 통과
- [x] Verified live (운영 DB 사본 + 실제 거래소 호출): KRW-ADA 4,327→8,752봉(365일), BTC/ETH 4시간봉 1,080→2,189봉. 백필 1회 30요청/4.4초 후 정상 상태 2요청으로 복귀(= 매번 재호출 없음). 상장 1년 미만 코인(KRW-BLEND)은 매 실행 4요청으로 제한(전체 재수집이었다면 26요청). 레짐 종목까지 깊어진 뒤 KRW-ADA 표본 n=2→13, 스캔 성능 40개 코인 환산 24초
- [ ] **미배포**: 코드 변경만 완료. 다음 파이프라인 실행 시 자동으로 백필이 시작되며, 최초 1회는 실행 시간이 약 2분 늘어남

### 🔁 Follow-up Request (2026-08-11): 바이낸스 전용 + 레짐 게이트 + 진입가/손절가/매도가
- [x] 조사 — "80% 확률" 요구를 구현 전에 실측으로 검증하고 **달성 불가**로 보고(1년/3년/5년 모두 +3% 터치 상한 46~48%, 강한상승 조건부 58.0%). 구름 돌파 가설도 기각(강한상승에서 48.0%로 기저 50.0% 미만). 기대수익률 4% 임계값이 실제 분포 최댓값(+2.68%)보다 높아 구조적으로 통과 불가였음을 확인 — 누적 추천 0건의 직접 원인
- [x] 표본 확대 — 1년 -> 3년 -> **5년**(2021-08~, 126만봉, 21분기, 2021 고점·2022 폭락·2024 상승장 포함). 별도 분석 DB 사용(운영 DB는 365일 유지)
- [x] **분석 코드 버그 자체 발견 및 정정** — bool Series에 `~`를 object dtype 상태로 적용해 "구름 돌파"가 "구름 위 상태"로 측정되고 있었음. 조합 결과가 원본과 완전히 일치하는 것을 보고 발견. 수정 후 해당 시그널은 16/21 -> 13/21로 유의성 소멸(보고 정정함)
- [x] Requirements Analysis — 사용자 결정: 진입 조건 C1(거래량돌파∩추세지속), 손절 -2% 적용 및 확률도 그 기준, 목표 +3%, 바이낸스 전용
- [x] Functional Design — Unit 1 BR12(바이낸스 전용 수집), Unit 2 BR18~BR21(매매 규칙/진입 조건/레짐 게이트/추천 하한). 기존 BR4·BR5·BR7 폐기
- [x] Code Generation — `src/backtest.py` 전면 교체(레이스 시뮬레이션, 레짐 판정, Wilson 하한, 골든크로스 계열 제거), `src/scorer.py`, `src/pipeline.py`(업비트 제거), `src/api.py`(stop_price/hit_rate/hit_rate_lower), `src/notifier.py`, README. 테스트 137/137 통과
- [x] Verified — 운영 코드가 분석 스크립트를 재현(898매매 목표달성 41.6% vs 분석값 40.7~42.9%). 과거 강한상승 시점(2025-05-22T16:00Z)으로 되감아 실전 코드 경로 통과 확인: WLDUSDT 진입 1.516 / 매도 1.56148(+3%) / 손절 1.48568(-2%) / 확률 40.9%(n=44) / 청산기한 +24h, 파생값 3종 모두 일치
- [ ] **미배포** — 현재 레짐이 None(하락장)이므로 배포해도 추천은 나오지 않습니다. 게이트가 열리는 시간은 5년 기준 약 19%

## Current Status
- **Lifecycle Phase**: COMPLETE (base project) + 6 follow-up features delivered (Docker Compose infra; 추천 결과 적중 판별; 바이낸스/업비트 거래소별 추천 5개씩 포함; 추천 발생 빈도 개선; 추천 신뢰도 향상; 진입 가이드 및 24시간 유효기간)
- **Current Stage**: 바이낸스 전용 재설계 완료, 배포 대기 (2026-08-11). Operations remains a placeholder with no defined steps (per core-workflow.md)
- **Next Stage**: None — all delivered work approved. Future work would re-enter as a new AI-DLC request (e.g. "Using AI-DLC, add X")
- **Status**: Done

### 🔁 Follow-up Request (2026-08-18): BTC/ETH 강세장 구분 문구 출력
- [x] Requirements Analysis — 요청의 갈림길 4개를 질문 파일로 정리(`requirement-verification-questions.md`). 사용자가 구간 정의를 직접 지시("일 주 30일, 월, 년 데이터 전체")하여 5구간(1일/7일/30일/90일/365일)으로 확정. **적용 범위는 표시 전용으로 판단** — 요청이 "문구도 바꿔서 출력"이었고, 게이트를 바꾸면 발표 중인 적중률이 측정 조건과 어긋남
- [x] Functional Design — Unit 2 analytics-backtest BR23(5구간 모멘텀, 자산별 강/약/비상승, BTC·ETH 합의 규칙), Unit 3 api-service BR23(알림 문구·API 노출). Unit 1 data-pipeline은 규칙 변경 없음(ETHUSDT 4h 수집 추가뿐)
- [x] Code Generation — `src/market_phase.py`(신규), `src/scorer.py`(`check_market_phase`, `PHASE_MARKETS`), `src/pipeline.py`(ETH 수집 + phase 전달), `src/notifier.py`(문구 렌더링), `src/api.py`(`market_phase` 응답 필드). 테스트 22개 추가, 전체 **194/194 통과**
- [x] 측정으로 규칙 1건 기각 — 느슨한 결합("하나라도 상승이면 약상승장")을 먼저 구현했다가 라이브 데이터에서 BTC 365일 -45.0%인데 헤드라인이 "약상승장"으로 나오는 것을 확인하고 합의 요구 규칙으로 교체
- [x] 실측 기록 — 강상승장 4% / 약상승장 26% / 상승장 아님 70%, 그 시점 BTC 30일 중앙값 +36.0% / +12.1% / -3.5%로 단조 분리. 예측력은 BR20-c 기준(에피소드 15건 중 양수 9건, 6건이 2024-11 편중)에 걸려 **주장하지 않음**
- [x] Verified live — 실 DB 백업 후 ETHUSDT 4h 12,209봉 신규 수집, 실제 발송 메시지 렌더링 확인, `GET /recommendations` 200 + `market_phase` 정상, `GET /health` 200

### 🔁 Follow-up Request (2026-08-18): 백테스트 이력 5년 → 12년 확대
- [x] Requirements Analysis — 사용자 질의("5년보다 많으면 확률이 높게 나오나")를 실측으로 답한 뒤, 사용자가 확대 결정. 문턱(45%) 조정은 **별도 건으로 분리** 지시받음
- [x] 측정 — 표본 539 → 1,153(2.1배), 적중률 38.2% → 36.9%, 신뢰구간 반폭 ±4.1%p → ±2.8%p. **확대는 확률을 높이는 게 아니라 정확하게 만든다**
- [x] 사용자 가설 검증 후 기각 — 반감기 4년 주기: 매매 적중률이 0~1년차 33.6%로 오히려 최저이고, 두 사이클이 서로 재현되지 않음(1~2년차 부호 반대). 끝까지 관측된 사이클 1개뿐이라 BR20-c ③④ 적용(2026-08-18 정정: 최초 '2개' 기록은 반감기 사건 수였고 완전 사이클 수가 아님). 사이클 정렬 lookback 미도입
- [x] 2026-08-12 "5년이 실질적 최대" 결정 뒤집음 — 당시엔 "표본이 충분한가"만 봤고 "추정이 정확한가"를 재지 않았음. 근거를 business-rules.md BR21 보강(2026-08-18)에 기록
- [x] Code Generation — `config/settings.yaml`(1825→4380), `src/config.py`(기본값), `src/binance_client.py`(`_MAX_PAGES` 60→130). **절단 결함 재발 방지**: 60페이지는 6.8년에서 조용히 잘려 12년 설정이 무효화됐을 것
- [x] Verified live — 실 DB 백업 후 백필 136초, 8종 확장(BNB 43,940→76,848 등) / 12종 무변화(상장 자체가 늦음), BTC·ETH 4h 2017-08-17까지. 봉 수가 별도 수집분과 정확히 일치해 절단 없음 확인. 풀스캔 47.3초, DB 155MB→180MB. 194/194 통과
- [ ] **미착수(사용자 지시로 분리)**: MIN_HIT_RATE 45% 문턱 조정 — 워크포워드상 필터 실제 우위 +2.6%p, 표시값 대비 -6.1%p
- [x] **(2026-08-18b) lookback 12년 → 16년** — 재측정 결과 데이터 증가 0(거래소 상한 9.0년), 통합 n=1,277/37.0%/±2.6%p로 12년과 동일. 측정 중 **직전 변경이 만든 회귀 발견·수정**: 매 실행 전량 재수집(136초 → 9초). `_MAX_PAGES` 130→150. 196/196 통과

### 🔁 Follow-up Request (2026-08-18): 장기/단기 2트랙 추천 (BR24)
- [x] Requirements Analysis — 사용자 전제 4개를 실측 검증: **반감기 장기 상승 확인**(3사이클 3/3 재현), **"단기=하락장 반등" 반증**(강한상승 37.5% vs 반등 33.7%), **"이미 크게 오른 놈" 반증**(필터로 쓰면 두 사이클 모두 기저 미만), **"거래량 실린 것" 확인**(0~1년차 결합 시 +12.6%p/+10.7%p 일관). "구름 뚫는 순간"은 기각, **"구름 위 상태"**로 정정
- [x] 데이터 소스 확장 — 바이낸스는 완전 사이클 1개뿐이라 Bitstamp BTC/USD 일봉 14.9년(완전 사이클 3개)을 **측정용**으로 사용. 운영 파이프라인에는 미편입
- [x] Functional Design — Unit 2 BR24(사이클 게이트·진입조건·매매규칙·연차별 표본), Unit 3 BR24(트랙 구분 저장·알림 섹션·유효기간·감시·API)
- [x] Code Generation — `src/long_track.py` 신규 + 6개 모듈 변경, `recommendations` PK 재구성, 테스트 24건 추가 → **220/220 통과**
- [x] 구현 중 결함 1건 발견·수정 — 진행 중인 매매를 타임아웃으로 집계해 ACE 표본이 27건(실제 3건)으로 부풀고 잘못된 추천이 발생. 단기 트랙과 동일하게 "창 미충족 시 판정 불가" 규칙 적용
- [x] Verified live — 사이클 2년차 개방, 장기 추천 0건이 정당함을 종목별로 실증(표본 하한이 신규 상장 종목을 정확히 차단)
- [x] 확정 파라미터 — 게이트 0~1·2~3년차 / 4시간봉 / 구름 위 + 거래량비>1.3 / **+20%·-10%** / 90일 / 후보 상위 15 / 표본 하한 10 / 적중률 문턱 없음
- [ ] **미착수**: 단기 트랙 MIN_HIT_RATE 45% 문턱 조정(사용자가 별건으로 분리)

### 🔁 Follow-up Request (2026-08-19): 4트랙 재편 (BR25) — BR24 대체
- [x] Requirements Analysis — 사용자 요청 전제 3건 측정: **"반감기 1년 전 강세장 95%" 반증**(엄격 기준 22~27% vs 기저 23.5%), **"4시간 구름대" 확인**(초단기 25.1%·단기 14.6%로 1위), **"1m/3m/5m 취합" 기각**(23GB 대비 이득이 창마다 부호 반전)
- [x] 요청 목표 실현 가능성 측정 — 단기 +5%는 24.8%(현행 +3% 36.3%), **장기 48시간 +15%는 8.7~16.7%로 성립 불가** → 사용자 지시로 "+10%/-7%/7일"(32%)로 재설정
- [x] Functional Design — Unit 2 BR25(4트랙·구름돌파·국면 3단계·수집 타임프레임), Unit 3 BR25(트랙 키 분리·섹션 5개·트랙별 규칙)
- [x] Code Generation — `src/tracks.py` 신규, `src/long_track.py`+테스트 **삭제**(BR24 철회), 6개 모듈 변경, 테스트 17건 추가 → **213/213 통과**
- [x] 절단 결함 예방 — 15분봉에 전체 lookback 적용 시 316페이지로 `_MAX_PAGES`(150) 초과 → **타임프레임별 lookback 분리**(15m 2년/30m 3년) + 가드 테스트를 타임프레임별 검사로 확장
- [x] Verified live — 7개 타임프레임 수집(15종, 15m 1,393,230봉 등), 국면 "상승장" 개방 확인, 4트랙 0건이 신호 부재 때문임을 종목별 실증(표본 하한은 13~15/15종 통과, n=188~1224)
- [ ] **미해결 — 사용자 결정 필요**: 초단기 -0.15% / 단기 -0.06% / 중기 +0.01% / 장기 +0.19%로 **초단기·단기 기대수익이 음수**(수수료 제외 기준). 거래량 필터는 도달률을 올리지만 기대수익을 더 낮춰 채택하지 않음
- [ ] **미착수**: 단기 트랙 MIN_HIT_RATE 45% 문턱 조정
- [x] **(2026-08-19) BR26 보조지표 + 문턱 조정** — 문턱 45%→30%/25%, 보조지표 RSI>=50+BTC구름위 채택, 초단기 포함 4트랙 모두 개방 국면 전체에서 동작(트랙별 전용 국면 없음 — 2026-08-19 오독 정정). **자기 정정**: 직전 보고한 보조지표 효과가 룩어헤드였음(시가 조회 → 마감 조회로 수정, 일봉 조건 폐기). 확정 기대수익 초단기 -0.05% / 단기 +0.04% / 중기 +0.07% / 장기 +0.40%. 222/222 통과
- [x] **(2026-08-19) BR27 골든크로스 + 판정 해상도 분리** — 진입 신호 교체, 판정봉 30분으로 분리, 장기만 구름 위 조건. **네 트랙 모두 기대수익 양수 전환**(초단기 -0.03%→+0.15%, 장기 +0.37%→+1.09%). 진입봉은 트랙 무관 4시간봉이 최적(통념 반증). 산출 53초→10초. 222/222 통과
