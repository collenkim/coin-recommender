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

## Current Status
- **Lifecycle Phase**: COMPLETE (base project) + 6 follow-up features delivered (Docker Compose infra; 추천 결과 적중 판별; 바이낸스/업비트 거래소별 추천 5개씩 포함; 추천 발생 빈도 개선; 추천 신뢰도 향상; 진입 가이드 및 24시간 유효기간)
- **Current Stage**: 백테스트 이력 365일 확대 코드 완료, 배포 대기 (2026-08-11). Operations remains a placeholder with no defined steps (per core-workflow.md)
- **Next Stage**: None — all delivered work approved. Future work would re-enter as a new AI-DLC request (e.g. "Using AI-DLC, add X")
- **Status**: Done
