# AI-DLC Audit Log

## Initial Request
**Timestamp**: 2026-08-06T00:00:00Z
**User Input**: "Using AI-DLC fastapi 파이썬 코드로 코인 추천 서비스를 만들려고해. ## 목표
1시간봉/4시간봉 데이터 기준으로 하루 안에 +4% 상승 가능성이 높은
알트코인을 추천한다.

## 데이터 소스
- 후보군: 업비트 KRW 마켓, 24h 거래대금 상위 20개 알트코인
  (BTC/ETH 제외)
- 시장 레짐 참고: 바이낸스 공개 API에서 BTC/ETH 데이터
  (유동성 높아 노이즈 적음, 인증 불필요한 /api/v3/klines 사용)

## 전략: 일목균형표(구름대)
- 4시간봉: 구름대 위 + 양운 여부로 추세 필터
- 1시간봉: 전환선/기준선 골든크로스로 진입 타이밍
- 바이낸스 BTC/ETH 4시간봉 구름대가 하락이면 전체 알트 점수에
  페널티

## 데이터 수집/저장
- 최초 실행 시 부트스트랩: 타임프레임당 최소 100봉
  (일목균형표 스팬B 52 + 26기간 선행이동 고려)
- 이후 매 실행마다 마지막 저장 시각 이후 캔들만 증분 수집
- SQLite에 (market, timeframe, candle_time) unique key로 upsert
- 업비트 종목 테이블과 바이낸스 참고종목 테이블 분리

## 추천 로직 (기대수익률 기반)
- 규칙기반 점수가 아니라 "동일 시그널 상태의 과거 실제 24시간
  수익률 평균"을 기대수익률로 계산
- 기대수익률 4% 이상인 코인만 추천 리스트에 포함 (미달이면 그
  코인은 제외, 어떤 날은 추천 결과가 0개일 수 있음)
- 결과에 샘플 수(N)도 같이 표시 (예: "기대수익률 5.1%
  (과거 3회 중 2회 적중)")

## 아키텍처
- FastAPI + APScheduler (인프로세스, lifespan에서 스케줄러 시작)
- GET /recommendations : 최신 추천 결과 조회
- POST /run : 수동 트리거
- 저장: SQLite
- 알림: 텔레그램/디스코드 웹훅 (requests로 직접 POST)

## 라이브러리
pyupbit, requests, pandas, pandas-ta(ichimoku), sqlite3(표준),
APScheduler, pydantic-settings, fastapi, uvicorn, logging(표준)

## 프로젝트 구조
coin-recommender/
├── config/settings.yaml
├── src/
│   ├── upbit_client.py
│   ├── binance_client.py
│   ├── market_selector.py
│   ├── data_store.py
│   ├── features.py       # 일목균형표 계산
│   ├── scorer.py          # 기대수익률 계산 (backtest 참조)
│   ├── backtest.py        # 시그널별 과거 수익률 통계
│   ├── notifier.py
│   ├── scheduler.py
│   └── api.py              # FastAPI 앱
├── tests/
└── requirements.txt

## 환경
Python 3.11+, IntelliJ venv 사용 예정

이 스펙대로 프로젝트 구조부터 잡고, 데이터 수집 →
저장(upsert) → 일목균형표 계산 순서로 단계별로 구현해줘.
각 단계마다 검증 방법(테스트/실행 결과)도 같이 알려줘."
**AI Response**: Started AI-DLC workflow. Displayed welcome message. Proceeding to Workspace Detection.
**Context**: Workflow trigger phrase "Using AI-DLC" detected. New software development request.

---

## Workspace Detection
**Timestamp**: 2026-08-06T00:00:01Z
**User Input**: N/A (automatic stage)
**AI Response**: Scanned workspace. No existing source code found (only .idea/, CLAUDE.md, .aidlc-rule-details/ from AI-DLC setup). Classified as Greenfield project. Created aidlc-docs/aidlc-state.md. Auto-proceeded to Requirements Analysis.
**Context**: Stage: Workspace Detection (ALWAYS). No approval required (informational only).

---

## Requirements Analysis — Clarifying Questions Created
**Timestamp**: 2026-08-06T00:00:02Z
**User Input**: N/A (AI-initiated)
**AI Response**: Detected one internal contradiction in the spec (rule-based BTC/ETH regime "penalty" vs. stated pure expected-return/data-driven scoring approach) plus 6 other design ambiguities (backtest history depth, per-coin vs pooled signal-state sampling, notification trigger condition, scheduler timing, /recommendations response scope, API auth exposure). Created aidlc-docs/inception/requirements/requirement-verification-questions.md with 7 substantive questions plus 3 extension opt-in questions (Security Baseline, Resiliency Baseline, Property-Based Testing). Waiting for user answers.
**Context**: Stage: Requirements Analysis (ALWAYS). Gate: awaiting user answers before Step 7 (requirements.md generation).

---

## Requirements Analysis — User Answered Questions
**Timestamp**: 2026-08-06T00:00:03Z
**User Input**: "완료" (User filled in all [Answer]: tags in requirement-verification-questions.md. Full answers: Q1=B (BTC/ETH regime as hard filter, no recommendation generation when bearish), Q2=B (collect separate long-period 6-12mo history for backtest), Q3=A (per-coin individual signal-state sampling, no pooling), Q4=A (always notify every run, even 0 results), Q5=A (hourly run, 5min after 1h candle close), Q6=A (latest run only, no history endpoint), Q7=A (local/personal use, no auth), Security Extension=A (enforce full baseline, blocking), Resiliency Extension=A (enforce full baseline, blocking), PBT Extension=B (partial enforcement: PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 only). See requirement-verification-questions.md for full text.)"
**AI Response**: Read full extension rule files (security-baseline.md, resiliency-baseline.md, property-based-testing.md) since Security and Resiliency were opted in. Detected a blocking contradiction: SECURITY-08 (deny-by-default authentication on all routes) directly conflicts with Q7=A (no auth, local personal use). Also detected a scope mismatch: Resiliency Baseline full enforcement requires production-cloud decisions (RTO/RPO, DR strategy, multi-region, CI/CD, change management, incident response) that don't fit a single-user local automation tool with no cloud deployment. Created requirement-verification-clarification-questions.md. Halting before Step 7 until resolved.
**Context**: Stage: Requirements Analysis. Contradiction/ambiguity detection per question-format-guide.md.

---

## Requirements Analysis — Clarification Round 2 Answered
**Timestamp**: 2026-08-06T00:00:04Z
**User Input**: "안만들어졌는데?" then, after confirming file existed on disk (IDE reload needed), user filled in requirement-verification-clarification-questions.md: Clarification 1 = A (keep Security Baseline enforced; mark SECURITY-08 as N/A — local personal use, no external exposure; all other security rules apply as-is). Clarification 2 = B (mark cloud-infrastructure Resiliency rules as N/A — local single instance, no cloud deployment; apply only code-level items: timeouts on external calls, retry/backoff, graceful degradation, /health endpoint).
**AI Response**: Both answers resolve cleanly with no further contradictions. Finalized extension enforcement scope. Proceeding to Step 7: generate requirements.md.
**Context**: Stage: Requirements Analysis. Gate passed — proceeding to requirements document generation.

---

## Requirements Analysis Complete
**Timestamp**: 2026-08-06T00:00:05Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Generated aidlc-docs/inception/requirements/requirements.md (14 functional requirements, security/resiliency/PBT NFRs scoped per extension decisions, key design decisions table, 2 documented assumptions: backtest_lookback_days default=180d, "적중" defined as actual 24h return >= +4%). Updated aidlc-state.md: Requirements Analysis marked complete. Assessed User Stories stage as likely-skip (single personal user, no persona/stakeholder complexity) pending user confirmation. Presenting completion message with Request Changes / Add User Stories / Approve & Continue options.
**Context**: Stage: Requirements Analysis (ALWAYS). Awaiting user approval before proceeding to Workflow Planning.

---

## Requirements Analysis - Approval
**Timestamp**: 2026-08-06T00:00:06Z
**User Input**: "Approve & Continue"
**AI Response**: Approval recorded. Proceeded to Workflow Planning (User Stories confirmed skipped per prior assessment, no override requested).
**Context**: Requirements Analysis approved, moving to Workflow Planning stage.

---

## Workflow Planning
**Timestamp**: 2026-08-06T00:00:07Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Generated aidlc-docs/inception/plans/execution-plan.md. Decided: Application Design EXECUTE, Units Generation EXECUTE (3 units: data-pipeline, analytics-backtest, api-service, sequenced per user's requested build order), per-unit Functional Design/NFR Requirements/NFR Design EXECUTE, Infrastructure Design SKIP (no cloud infra), Code Generation and Build and Test EXECUTE (always). Risk level: Medium. Created 7 tracking tasks (#1-#7) for the remaining workflow. Updated aidlc-state.md. Presenting plan for approval.
**Context**: Stage: Workflow Planning (ALWAYS). Awaiting user approval before proceeding to Application Design.

---

## Workflow Planning - Approval
**Timestamp**: 2026-08-06T00:00:08Z
**User Input**: "Approve & Continue"
**AI Response**: Approval recorded. Proceeded to Application Design stage.
**Context**: Execution plan approved, moving to Application Design.

---

## Application Design - Plan Created
**Timestamp**: 2026-08-06T00:00:09Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created aidlc-docs/inception/plans/application-design-plan.md. Adopted user's given 9-file component structure as-is (no re-question). Pre-decided 4 low-ambiguity design items (regime filter location, secrets via .env, pydantic models for inter-component data). Asked 1 targeted question: where should pipeline orchestration (shared by POST /run and scheduler) live. Waiting for answer.
**Context**: Stage: Application Design. Gate: awaiting user answer before generating design artifacts.

---

## Application Design - Artifacts Generated
**Timestamp**: 2026-08-06T00:00:10Z
**User Input**: "답변했어." (Answered orchestration question: B — new pipeline.py file for shared orchestration)
**AI Response**: Generated components.md, component-methods.md, services.md, component-dependency.md, application-design.md. Discovered and corrected a unit-boundary dependency conflict during design: moved BTC/ETH regime hard-filter logic from binance_client.py (Unit 1) to scorer.py (Unit 2), since it requires features.py's ichimoku calculation (Unit 2) and Unit 1 builds before Unit 2 — kept dependency direction Unit1 -> Unit2 -> Unit3 with no reversal. Documented this correction transparently in components.md for user override if needed. Included extension compliance summary (Security/Resiliency/PBT — mostly N/A at this stage, 3 items compliant).
**Context**: Stage: Application Design. Awaiting user approval before proceeding to Units Generation.

---

## Application Design - Approval
**Timestamp**: 2026-08-06T00:00:11Z
**User Input**: "Approve & Continue"
**AI Response**: Approval recorded. Proceeded to Units Generation (Part 1 - Planning).
**Context**: Application Design approved, moving to Units Generation.

---

## Units Generation - Part 1 Planning
**Timestamp**: 2026-08-06T00:00:12Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created unit-of-work-plan.md. Evaluated all 6 mandatory question categories; found no open questions since decomposition/dependencies were already settled in Workflow Planning and Application Design, and remaining categories (team alignment, deployment scaling) are N/A for a solo local monolith. Requested approval to proceed directly to generation.
**Context**: Stage: Units Generation Part 1. Awaiting user approval before Part 2 (Generation).

---

## Units Generation - Part 2 Generation
**Timestamp**: 2026-08-06T00:00:13Z
**User Input**: "다음 단계로 실행해줘."
**AI Response**: Generated unit-of-work.md (3 units, flat src/ code organization per user's original structure), unit-of-work-dependency.md (Unit1->Unit2->Unit3, no cycles), unit-of-work-story-map.md (FR1-FR14 mapped to units, no gaps — adapted from story-map since User Stories was skipped). Marked all plan checkboxes [x]. Updated aidlc-state.md: Units Generation complete, INCEPTION phase substantively done pending final approval to enter CONSTRUCTION.
**Context**: Stage: Units Generation Part 2. Awaiting user approval before entering CONSTRUCTION PHASE.

---

## Units Generation - Approval / CONSTRUCTION PHASE Entry
**Timestamp**: 2026-08-06T00:00:14Z
**User Input**: "Approve & Continue"
**AI Response**: Approval recorded. INCEPTION phase complete. Entered CONSTRUCTION PHASE, starting Unit 1 (data-pipeline) Functional Design.
**Context**: Transition from INCEPTION to CONSTRUCTION phase.

---

## Functional Design - Unit 1 (data-pipeline)
**Timestamp**: 2026-08-06T00:00:15Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created data-pipeline-functional-design-plan.md. Evaluated question categories; resolved 4 items via sound engineering defaults (UTC timestamp normalization, insufficient-history exclusion rule, rate-limit-aware sequential fetch, shared upsert target for bootstrap+backtest history) rather than opening new questions, since these are technical implementation details with clear best-practice answers, not business ambiguities. Generated business-logic-model.md, business-rules.md (7 rules), domain-entities.md (Candle, TickerInfo, CollectionResult). Identified 2 testable properties for later PBT (round-trip, idempotence on upsert).
**Context**: Stage: Functional Design (Unit 1). Awaiting user approval before NFR Requirements (Unit 1).

---

## Functional Design - Unit 1 Approval
**Timestamp**: 2026-08-06T00:00:16Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to NFR Requirements (Unit 1).
**Context**: Functional Design (Unit 1) approved.

---

## NFR Requirements - Unit 1 (data-pipeline)
**Timestamp**: 2026-08-06T00:00:17Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created data-pipeline-nfr-requirements-plan.md. No new questions needed (all categories resolved via prior decisions or standard engineering defaults). Generated nfr-requirements.md (performance soft-target, reliability: 10s timeout + 3 retries exponential backoff, security: no credentials needed since both exchange endpoints used are public) and tech-stack-decisions.md (confirms user's originally specified stack, no new libraries introduced).
**Context**: Stage: NFR Requirements (Unit 1). Awaiting user approval before NFR Design (Unit 1).

---

## NFR Requirements - Unit 1 Approval
**Timestamp**: 2026-08-06T00:00:18Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to NFR Design (Unit 1).
**Context**: NFR Requirements (Unit 1) approved.

---

## NFR Design - Unit 1 (data-pipeline)
**Timestamp**: 2026-08-06T00:00:19Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created data-pipeline-nfr-design-plan.md, no new questions. Generated nfr-design-patterns.md (retry+backoff helper, no circuit breaker, 100ms inter-request delay for Upbit, SQLite WAL mode + short-lived connections for scheduler/API concurrency safety) and logical-components.md.
**Context**: Stage: NFR Design (Unit 1). Awaiting user approval before Code Generation (Unit 1).

---

## NFR Design - Unit 1 Approval
**Timestamp**: 2026-08-06T00:00:20Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to Code Generation (Unit 1) Part 1 - Planning.
**Context**: NFR Design (Unit 1) approved.

---

## Code Generation - Unit 1 Planning
**Timestamp**: 2026-08-06T00:00:21Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created data-pipeline-code-generation-plan.md, 7 steps. Flagged 2 additions beyond the user's original file list: src/config.py (needed to house the pydantic-settings Settings class the user explicitly requested but didn't allocate a file for) and tests/generators.py (shared Hypothesis Candle generator, PBT-07 reusability). Requesting plan approval before generation.
**Context**: Stage: Code Generation (Unit 1) Part 1. Awaiting user approval before Part 2 (Generation).

---

## Code Generation - Unit 1 Generation
**Timestamp**: 2026-08-06T00:00:22Z
**User Input**: "Ready to proceed to generation"
**AI Response**: Generated all Unit 1 files (config.py, data_store.py, upbit_client.py, binance_client.py, market_selector.py, tests, config/settings.yaml, .env.example, .gitignore, requirements.txt, README.md). No Python 3.11+ interpreter was available on this machine (only WindowsApps stub and py.exe 3.6.8); asked the user how to proceed and, per their choice, installed Python 3.11.9 via winget, created venv, installed dependencies, and actually ran the test suite. Found and fixed 2 real issues during execution: (1) a test assertion bug in test_get_ohlcv_retries_on_connection_error_then_succeeds that didn't account for the rate-limit sleep call, (2) a real production bug in config.py -- YAML file read without explicit UTF-8 encoding, causing UnicodeDecodeError on Korean Windows (cp949 default) when parsing the Korean comments in settings.yaml; fixed with yaml_file_encoding="utf-8". All 21 tests pass after fixes.
**Context**: Stage: Code Generation (Unit 1) Part 2. Awaiting user approval before Unit 2 (analytics-backtest).

---

## Code Generation - Unit 1 Approval / Unit 1 Complete
**Timestamp**: 2026-08-06T00:00:23Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Unit 1 (data-pipeline) fully complete (Functional Design, NFR Requirements, NFR Design, Code Generation all approved). Starting Unit 2 (analytics-backtest) Functional Design.
**Context**: Unit 1 complete. Entering Unit 2 per-unit loop.

---

## Functional Design - Unit 2 (analytics-backtest) - Plan Created
**Timestamp**: 2026-08-06T00:00:24Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created analytics-backtest-functional-design-plan.md. Pre-decided 5 items with rationale (no chikou span since unused by strategy, standard cloud/bullish-cloud definitions, simplified signal-state to a single composite condition rather than the multi-dimensional framing from requirements.md, excluded too-recent signals from backtest samples since 24h outcome unobservable, live evaluation uses only fully-closed candles). Identified 2 real open trade-offs affecting statistical validity requiring user judgment: (1) golden-cross as event vs sustained state, (2) whether historical backtest samples should be filtered by the BTC/ETH regime that was in effect at that historical time. Waiting for answers.
**Context**: Stage: Functional Design (Unit 2). Gate: awaiting user answers.

---

## Functional Design - Unit 2 - Round 1 Answered, Follow-up Raised
**Timestamp**: 2026-08-06T00:00:25Z
**User Input**: "답변했어." (Q1=A event-based golden cross, Q2=A regime-consistent historical backtest sampling)
**AI Response**: Answers are mutually consistent, no contradiction. While working out the exact algorithm for Q2 (regime-consistent sampling), discovered the spec never defined how to combine BTC and ETH into a single regime verdict (AND/OR/BTC-only) -- this materially affects both live filtering frequency and backtest sample size. Added Question 3 as a mandatory follow-up per functional-design.md Step 8, appended to the same plan file. Waiting for answer.
**Context**: Stage: Functional Design (Unit 2). Gate: awaiting answer to follow-up Question 3.

---

## Functional Design - Unit 2 - Complete
**Timestamp**: 2026-08-06T00:00:26Z
**User Input**: "답변 했어." (Q3=A: AND -- both BTC and ETH must be bullish for regime)
**AI Response**: All 3 answers consistent, no contradictions. Generated domain-entities.md (IchimokuPoint, RegimeStatus, SignalStats, Recommendation), business-rules.md (10 rules with exact Ichimoku formulas, explicit senkou span alignment convention to prevent a common shift-direction bug, as-of 4h/1h join rule, full backtest sampling algorithm), business-logic-model.md (regime gate flow, live signal flow, backtest sampling flow, 4 testable properties including PBT-03 invariants that are enforced under partial PBT mode).
**Context**: Stage: Functional Design (Unit 2). Awaiting user approval before NFR Requirements (Unit 2).

---

## Functional Design - Unit 2 Approval
**Timestamp**: 2026-08-06T00:00:27Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to NFR Requirements (Unit 2).
**Context**: Functional Design (Unit 2) approved.

---

## NFR Requirements - Unit 2 (analytics-backtest)
**Timestamp**: 2026-08-06T00:00:28Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created analytics-backtest-nfr-requirements-plan.md. Corrected a tech-stack direction error found while assessing this stage: functional-design.md had implied hand-rolling the ichimoku math directly, which would have silently dropped the user's explicitly requested pandas-ta library. Corrected to: production code uses pandas-ta's ichimoku(), verified via an oracle test against an independent pure-pandas reference implementation. Generated nfr-requirements.md (vectorized pandas performance requirement, reliability for insufficient-history coins) and tech-stack-decisions.md.
**Context**: Stage: NFR Requirements (Unit 2). Awaiting user approval before NFR Design (Unit 2).

---

## NFR Requirements - Unit 2 Approval
**Timestamp**: 2026-08-06T00:00:29Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to NFR Design (Unit 2).
**Context**: NFR Requirements (Unit 2) approved.

---

## NFR Design - Unit 2 (analytics-backtest)
**Timestamp**: 2026-08-06T00:00:30Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created analytics-backtest-nfr-design-plan.md, no new questions. Generated nfr-design-patterns.md (single-pass vectorized computation, silent skip on insufficient data, oracle test approach for pandas-ta verification) and logical-components.md (reference implementation lives in tests/ only, as-of matcher inside features.py).
**Context**: Stage: NFR Design (Unit 2). Awaiting user approval before Code Generation (Unit 2).

---

## NFR Design - Unit 2 Approval / Code Generation Planning
**Timestamp**: 2026-08-06T00:00:31Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Created analytics-backtest-code-generation-plan.md (8 steps: features.py, tests+oracle, backtest.py, tests, scorer.py, tests, doc summary, verify/regression). Requesting plan approval before generation.
**Context**: Stage: Code Generation (Unit 2) Part 1. Awaiting user approval before Part 2 (Generation).

---

## Code Generation - Unit 2 Generation
**Timestamp**: 2026-08-06T00:00:32Z
**User Input**: "Ready to proceed to generation"
**AI Response**: Attempted to install pandas-ta; found only beta releases (0.4.67b0/0.4.71b0) remain on PyPI, both requiring Python 3.12+, conflicting with the 3.11.9 venv from Unit 1. Asked the user how to proceed; they chose to upgrade to Python 3.12 and keep pandas-ta as originally requested. Installed Python 3.12.10 via winget, recreated venv, reinstalled all dependencies, confirmed Unit 1's 21 tests still pass (no regression). Empirically probed pandas-ta's actual ichimoku() output against hand-computed reference values and discovered it shifts cloud spans by 25 periods, not the textbook 26 -- corrected business-rules.md BR1 to match this measured behavior rather than the originally assumed convention. Generated features.py, backtest.py, scorer.py and their tests (features: 10, backtest: 11, scorer: 8 = 29 new tests). Found and fixed 2 more real bugs during execution: compute_ichimoku crashed on very short candle lists (pandas-ta returns (None, None) instead of a DataFrame) -- fixed; and an incorrect warmup-boundary test assumption (senkou_a and senkou_b have different warmup lengths, 50 vs 76) -- fixed. Full suite: 50/50 passed, no regressions. Pinned pandas==3.0.5 and pandas-ta==0.4.71b0 in requirements.txt, updated README.md to note the Python 3.12+ requirement change.
**Context**: Stage: Code Generation (Unit 2) Part 2. Awaiting user approval before Unit 3 (api-service).

---

## Code Generation - Unit 2 Approval / Unit 2 Complete
**Timestamp**: 2026-08-06T00:00:33Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Unit 2 (analytics-backtest) fully complete. Starting Unit 3 (api-service) Functional Design.
**Context**: Unit 2 complete. Entering Unit 3 per-unit loop (final unit).

---

## Functional Design - Unit 3 (api-service) - Complete
**Timestamp**: 2026-08-06T00:00:34Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created api-service-functional-design-plan.md with 5 pre-decided items (persisted pipeline_runs + recommendations tables to survive restarts and distinguish "0 results" from "never run", multi-channel notification, in-process lock against concurrent pipeline runs, notification failure does not roll back saved results, Korean notification format matching the spec's own example). No open questions -- all resolved with clear low-risk defaults. Generated domain-entities.md, business-rules.md (8 rules), business-logic-model.md.
**Context**: Stage: Functional Design (Unit 3). Awaiting user approval before NFR Requirements (Unit 3).

---

## Functional Design - Unit 3 Approval
**Timestamp**: 2026-08-06T00:00:35Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to NFR Requirements (Unit 3).
**Context**: Functional Design (Unit 3) approved.

---

## NFR Requirements - Unit 3 (api-service)
**Timestamp**: 2026-08-06T00:00:36Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created api-service-nfr-requirements-plan.md, no new questions. Generated nfr-requirements.md (security items mostly N/A or already-established, APScheduler coalesce/misfire_grace_time for reliability) and tech-stack-decisions.md (confirms user's specified stack, no new libraries beyond fastapi/uvicorn/apscheduler).
**Context**: Stage: NFR Requirements (Unit 3). Awaiting user approval before NFR Design (Unit 3).

---

## NFR Requirements - Unit 3 Approval
**Timestamp**: 2026-08-06T00:00:37Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Proceeded to NFR Design (Unit 3).
**Context**: NFR Requirements (Unit 3) approved.

---

## NFR Design - Unit 3 (api-service)
**Timestamp**: 2026-08-06T00:00:38Z
**User Input**: N/A (AI-generated artifact)
**AI Response**: Created api-service-nfr-design-plan.md, no new questions. Generated nfr-design-patterns.md (module-level lock, coalesced scheduler, global exception handler, best-effort notification) and logical-components.md.
**Context**: Stage: NFR Design (Unit 3). Awaiting user approval before Code Generation (Unit 3).

---

## NFR Design - Unit 3 Approval / Code Generation Planning
**Timestamp**: 2026-08-06T00:00:39Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Created api-service-code-generation-plan.md (12 steps). Notes DataStore and config.py as existing files to modify in-place (not duplicate). Requesting plan approval before generation.
**Context**: Stage: Code Generation (Unit 3) Part 1. Awaiting user approval before Part 2 (Generation).

---

## Code Generation - Unit 3 Generation
**Timestamp**: 2026-08-06T00:00:40Z
**User Input**: "Ready to proceed to generation?"
**AI Response**: Extended data_store.py (pipeline_runs/recommendations tables, save_run/get_latest_run/ping) and config.py in-place. Generated notifier.py, pipeline.py, scheduler.py, api.py and their tests (26 new tests across test_data_store additions, test_notifier, test_pipeline, test_api). Found and fixed a real design error before it became a silent bug: Telegram has no generic outbound webhook URL (unlike Discord) -- it requires a bot token + chat id via the Bot API's sendMessage endpoint. Corrected config.py/notifier.py/.env.example from a single TELEGRAM_WEBHOOK_URL to TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID. Full suite: 76/76 passed. Additionally booted the real server with uvicorn and confirmed GET /health returns 200 with a real DB connection, verifying full startup wiring (lifespan, scheduler, DB) actually works end-to-end, not just via mocks.
**Context**: Stage: Code Generation (Unit 3) Part 2. Unit 3 and all units complete. Awaiting user approval before Build and Test.

---

## Build and Test Stage
**Timestamp**: 2026-08-06T00:00:41Z
**Build Status**: Success
**Test Status**: Pass (76/76)
**User Input**: "Continue to Next Stage"
**AI Response**: Ran a real end-to-end smoke test: booted the actual server (not TestClient), called POST /run against the live Upbit and Binance APIs (no mocks), got a valid 200 response (regime_bullish=false, recommendations=[] -- a legitimate result since BTC/ETH cloud wasn't bullish at test time, not a bug), confirmed GET /recommendations correctly persisted and re-served the same run, and confirmed GET /health reports real DB connectivity. Server logs showed no errors/retries -- the full collection->storage->analysis->API chain works against reality, not just mocks. Found and fixed one more real gap: fastapi/uvicorn/apscheduler/httpx were unpinned in requirements.txt -- pinned to actually-installed versions. Generated all 5 build-and-test instruction files (build, unit-test, integration-test with the live-run results embedded, performance with soft-target verification, security with SECURITY-baseline checks) plus build-and-test-summary.md.
**Files Generated**:
- build-instructions.md
- unit-test-instructions.md
- integration-test-instructions.md
- performance-test-instructions.md
- security-test-instructions.md
- build-and-test-summary.md

---

## Build and Test - Approval / Project Complete
**Timestamp**: 2026-08-06T00:00:42Z
**User Input**: "Approve & Continue"
**AI Response**: Approval recorded. Operations phase is a placeholder per core-workflow.md (no defined steps -- build/test activities are handled in CONSTRUCTION). Marked aidlc-state.md as complete. coin-recommender project delivered: 3 units, 76/76 tests passing, live-verified against real Upbit/Binance APIs.
**Context**: AI-DLC workflow complete for this request.

---

## New Request - Workspace Detection (Resume)
**Timestamp**: 2026-08-07T00:00:00Z
**User Input**: "Using AI-DLC 서비스 띄우기 위한 인프라 환경은 docker-compose로 만들어줘. 그리고 업비트 open api 사용 가능한 형태인거야? 맞다면 api 키는 실행 단계에서 vm option으로 입력 받아서 처리될 수 있도록 해줘."
**AI Response**: Existing AI-DLC project detected (aidlc-state.md status: COMPLETE). Resuming as a new follow-up request per session-continuity.md. This is a Brownfield project with no code changes needed to workspace state; proceeding to Requirements Analysis. Read src/upbit_client.py, src/config.py, src/api.py, src/scheduler.py, requirements.txt to assess current Upbit integration before drafting requirements.
**Context**: Workspace Detection (resume) for new infra request.

---

## Requirements Analysis - Clarifying Questions
**Timestamp**: 2026-08-07T00:05:00Z
**User Input**: (see above)
**AI Response**: Code review confirms the current Upbit integration (src/upbit_client.py) uses only pyupbit's public/unauthenticated endpoints (get_ohlcv, get_tickers) plus the public REST ticker endpoint -- no access_key/secret_key or authenticated Upbit Open API calls exist anywhere in src/. Architecture is a single FastAPI process (in-process APScheduler, SQLite file DB) with no other services. Genuine ambiguities identified before writing docker-compose: (1) intended run mode (local dev vs. always-on server) affects restart policy and container hardening, (2) SQLite persistence approach (bind mount vs named volume), (3) whether to add unused Upbit auth-key plumbing proactively since none exists in code today, (4) confirming "VM option" maps to container runtime environment variables (Docker has no JVM-style -D flags). Created requirement-verification-questions.md and stopped for answers per requirements-analysis.md Step 6 gate.
**Context**: Requirements Analysis (Minimal-Standard depth) for docker-compose infra request.

---

## Requirements Analysis - Answers Received
**Timestamp**: 2026-08-07T00:10:00Z
**User Input**: "완료 했어." (answers filled into requirement-verification-questions.md: Q1=A 서버(VM)에서 상시 운영, Q2=A 호스트 ./data 바인드 마운트, Q3=A 현재 그대로 유지(인증 키 추가 안 함), Q4=B IntelliJ 실행 설정(로컬 비-컨테이너 실행 시))
**AI Response**: Read answers. Q1/Q3 resolve the two real forks: always-on VM deployment (not throwaway dev), and no Upbit auth-key plumbing since it's unused in code today. Q4's "IntelliJ Run Configuration" answer applies to non-container local runs only (pydantic-settings already reads process env vars there with priority over .env, no code change needed) -- it does not apply to the docker-compose path, where existing secrets (Telegram/Discord) still need runtime injection; used the project's existing `.env` convention (env_file) for that, consistent with Q4's spirit of "not baked into anything at build/commit time." No further contradictions found. Generated requirements.md (Step 7) and infrastructure-design.md (mapping: single container, bind-mount storage, no messaging/networking/monitoring stack beyond the existing GET /health reused as Docker healthcheck).
**Context**: Requirements Analysis Step 7 + Infrastructure Design, docker-compose follow-up request.

---

## Code Generation - Docker Compose Infra
**Timestamp**: 2026-08-07T00:20:00Z
**User Input**: (proceeding directly per already-answered requirements; no separate plan-approval round-trip requested)
**AI Response**: Generated Dockerfile (python:3.12-slim, pinned tag per SECURITY baseline, non-root `app` user, COPY src+config only), .dockerignore (excludes venv/.git/.idea/data/.env/tests/aidlc-docs from build context), docker-compose.yml (single `api` service, `env_file: .env`, bind mount `./data:/app/data`, `healthcheck` against existing GET /health, `restart: unless-stopped` per Q1), and a README "Docker로 실행" section. Verified live end-to-end: `docker compose config` validated, `docker compose build` succeeded, `docker compose up -d` reported the container `(healthy)`, `curl :8000/health` returned `{"status":"ok","db_connected":true}`, `curl :8000/recommendations` correctly read pre-existing data from the bind-mounted ./data DB, then `docker compose down` cleaned up. No Upbit access_key/secret_key added anywhere, confirming the answer to the user's original question: the app currently only uses Upbit's public API, so no key injection was needed.
**Files Generated**: Dockerfile, .dockerignore, docker-compose.yml
**Files Modified**: README.md (added Docker section)
**Context**: Code Generation for Docker Compose infra follow-up request.

---

## Code Generation - Approval / Docker Compose Infra Complete
**Timestamp**: 2026-08-07T00:25:00Z
**User Input**: "ntinue to Next Stage" (Continue to Next Stage)
**AI Response**: Approval recorded. Docker Compose infra follow-up request marked complete. Operations remains a placeholder per core-workflow.md.
**Context**: AI-DLC docker-compose follow-up request complete.

---

## Code Generation - Request Changes
**Timestamp**: 2026-08-07T00:26:00Z
**User Input**: "Request Changes"
**AI Response**: Request received without specifics. Asking user which part of the Docker Compose deliverable to change before modifying anything, rather than guessing.
**Context**: Docker Compose infra follow-up request — awaiting change details.

---

## Architecture Confirmation - Upbit/Binance Key Requirements
**Timestamp**: 2026-08-07T00:35:00Z
**User Input**: "업비트 API를 사용하려면 키가 필요한거잖아? 키를 전달하는 방법은 intellij 설정을 통해 전달하게 할꺼고, 그걸 받아서 처리하는 구조로 되어 있는지 확인해주고, 바이낸스 비트코인, 이더리움 정보도 참고할 수 있도록 한다고 했는데 그렇게 동작하는 구조인건지. 바이낸스 참조하려면 별도로 필요한게 있는지도 검토해줘."
**AI Response**: Investigated src/pipeline.py, src/upbit_client.py, src/binance_client.py, src/config.py. Corrected premise: Upbit's public market-data endpoints (candles, tickers) -- the only ones this app calls -- do not require access_key/secret_key at all; Upbit only requires keys for authenticated endpoints (orders, account balance), which this app never calls. Confirmed no structure exists to receive/process an Upbit key today: UpbitClient.__init__ takes no key params, Settings (src/config.py) has no upbit_access_key/upbit_secret_key field, so an IntelliJ env var of that name would currently be silently ignored (extra="ignore"). Confirmed Binance BTC/ETH regime reference is implemented and working: BinanceClient.get_klines (src/binance_client.py) calls the public /api/v3/klines endpoint, invoked from pipeline.py's run_recommendation_pipeline for BTC_MARKET/ETH_MARKET -- no API key needed for this endpoint either, already live-verified in the original Build and Test phase. No code changes made -- this was a confirmation/explanation request.
**Context**: Resolves the "Request Changes" -> "업비트 API 키 관련 결정 재검토" thread with factual clarification rather than adding unused key plumbing.

---

## Code Generation - Approval / Docker Compose Infra Complete
**Timestamp**: 2026-08-07T00:40:00Z
**User Input**: "구조에 대한 확인 목적이야."
**AI Response**: Confirmed the "Request Changes" was purely a request to verify Upbit/Binance key architecture, not a change to the Docker Compose deliverable. No code changes needed -- Dockerfile, .dockerignore, docker-compose.yml, and README stand as generated and previously verified live (build/up/healthcheck/curl/down). Docker Compose infra follow-up request marked complete.
**Context**: AI-DLC docker-compose follow-up request complete.

---

## New Request - Outcome Tracking / Adaptive Learning Feature
**Timestamp**: 2026-08-07T01:00:00Z
**User Input**: "Using AI-DLC 추천한 코인이 예측 도달 %에 부합했는지 아닌지 그 다음 동작에 판별하고, 기록하고 이런 데이터도 학습해서 좀 더 정교하게 맞출수 있도록 로직을 추가하거나 수정해줘."
**AI Response**: Read src/scorer.py, src/backtest.py, src/features.py, src/data_store.py, src/market_selector.py to understand current logic before analyzing the request. Confirmed: expected_return/n/hit_count today are computed purely retrospectively -- compute_signal_stats() scans the coin's own historical candles for past occurrences of the same composite signal (golden cross + 4h trend + regime bullish) and averages their realized 24h forward returns. There is no live outcome tracking: recommendations are written to the `recommendations` table (run_time, market, expected_return, n, hit_count) and never revisited afterward -- no column or mechanism records whether a specific recommendation actually hit its predicted return. Request type: New Feature (Enhancement), touching all 3 units (data-pipeline: new outcome data model; analytics-backtest: how outcome data feeds into stats; api-service: when/how evaluation runs and is exposed). Complexity: Complex -- multiple genuine ambiguities (what counts as "reached" the threshold, what "learning" concretely means, when evaluation runs, whether to backfill). This will require Requirements Analysis (Standard/Comprehensive depth) followed likely by Functional Design for the affected units (new data model + complex business logic triggers that stage per code-generation.md). Created requirement-verification-questions.md and stopped for answers per requirements-analysis.md Step 6 gate.
**Context**: Requirements Analysis for new outcome-tracking/adaptive-learning feature request.

---

## Requirements Analysis - Answers Received + Key Finding
**Timestamp**: 2026-08-07T01:15:00Z
**User Input**: Answers filled into requirement-verification-questions.md: Q1=B (고가 기준 24h 내 임계값 도달), Q2=A (백테스트 샘플 풀에 누적 반영), Q3=A (기존 스케줄러 내 처리), Q4=B (과거 기록도 소급 판별), Q5=A (GET /recommendations 확장)
**AI Response**: Re-examined compute_signal_stats (src/backtest.py) in light of the answers. Key finding: it already re-scans the FULL stored candle history for the market on every call, so as candle collection (Unit 1) keeps accumulating hourly, expected_return/n/hit_count automatically incorporate newer real market occurrences of the signal -- with zero new code. This means Q2=A's requested effect ("학습해서 정교하게") already happens automatically today; it does not need a new "feed live outcome into backtest pool" mechanism. Narrowed the real new-build scope to: recording+tracking whether specific past recommendation instances actually hit their target (audit/visibility), not improving the scoring algorithm itself (which was never disconnected from live data). Documented this in requirements.md as an explicit "Out of Scope: adaptive scoring algorithm changes" plus FR-L6 (compute_signal_stats stays unchanged). Presenting requirements.md for approval before proceeding to Functional Design (Unit 2 analytics-backtest + Unit 3 api-service -- Unit 1 data-pipeline needs no business-logic changes, so Functional Design will be skipped for it).
**Context**: Requirements Analysis Step 7-9, outcome-tracking feature request.

---

## Requirements Analysis - Approved
**Timestamp**: 2026-08-07T01:20:00Z
**User Input**: "Approve & Continue"
**AI Response**: Approval recorded. Proceeding to Functional Design for Unit 2 (analytics-backtest) and Unit 3 (api-service) -- Unit 1 (data-pipeline) skipped, no business-logic changes needed there.
**Context**: Outcome-tracking feature request.

---

## Functional Design - Unit 2 (analytics-backtest) + Unit 3 (api-service)
**Timestamp**: 2026-08-07T01:30:00Z
**User Input**: (proceeding per approved requirements; remaining decisions were implementation defaults, not user-facing forks, so no additional question file per functional-design.md Step 3's own precedent for low-risk defaults -- documented with rationale for Request Changes if wrong)
**AI Response**: Extended existing per-unit docs in-place (brownfield modification, not new files):
- Unit 2 business-rules.md: added BR11 (evaluate_outcome -- entry candle via as-of match on run_time, 24-bar window, target_reached via intra-window HIGH >= entry_close*1.04 per Q1=B, realized_return via same close-to-close formula as BR8 for consistency/NFR-L1) and BR12 (pending-evaluation selection, retry-forever-if-data-missing tradeoff documented as accepted for this scale).
- Unit 2 domain-entities.md: added RecommendationOutcome entity.
- Unit 2 business-logic-model.md: added evaluate_outcome pseudocode + a PBT invariant row.
- Unit 3 business-rules.md: added BR9 (evaluation batch runs inside run_recommendation_pipeline, same lock, isolated per-item failure) and BR10 (GET /recommendations limit param -- default preserves exact existing response shape, limit>1 adds a non-breaking `history` field rather than changing the top-level type).
- Unit 3 domain-entities.md: added 3 nullable columns to recommendations table (target_reached, realized_return, evaluated_at) + ALTER-TABLE-based migration note for NFR-L3 (already-deployed DB from the earlier docker-compose live test has existing rows).
- Unit 3 business-logic-model.md: added evaluate_pending_outcomes pseudocode and extended the GET /recommendations flow.
**Context**: Functional Design for outcome-tracking feature, presenting for combined approval (both units, one feature).

---

## Functional Design - Approved
**Timestamp**: 2026-08-07T01:35:00Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. NFR Requirements/NFR Design skipped for this feature (reuses existing SQLite/scheduler/FastAPI stack, no new infra or tech-stack decisions). Proceeding directly to Code Generation.
**Context**: Outcome-tracking feature request.

---

## Code Generation - Unit 2 (analytics-backtest) + Unit 3 (api-service)
**Timestamp**: 2026-08-07T02:00:00Z
**User Input**: (proceeding per approved functional design)
**AI Response**: Modified in-place (brownfield): src/backtest.py (RecommendationOutcome dataclass + evaluate_outcome per BR11), src/data_store.py (3 nullable columns on recommendations table + ALTER-TABLE migration guarded against duplicate-column errors, RecommendationRecord extended, get_pending_evaluations/record_outcome/get_recent_runs added, get_latest_run updated to select new columns), src/pipeline.py (evaluate_pending_outcomes per BR9, wired into run_recommendation_pipeline inside the existing lock after notification), src/api.py (RecommendationOut gained target_reached/realized_return, new RunSummary model, RecommendationsResponse gained optional history field, GET /recommendations gained limit query param per BR10). Added tests: test_backtest.py (evaluate_outcome hit/no-hit/no-entry-candle/incomplete-window), test_data_store.py (migration against a hand-built legacy schema, pending/record/recent-runs), test_pipeline.py (evaluate_pending_outcomes wiring + per-item failure isolation), test_api.py (outcome fields in response, limit param history). Full suite: 91/91 passed (up from 76). Live-verified against the REAL existing data/coin_recommender.db (created before this feature, missing the new columns) -- migration confirmed to add the 3 columns without error (checked via PRAGMA table_info before/after), then booted the actual server and called GET /health, GET /recommendations, GET /recommendations?limit=3 against it -- all returned correct, backward-compatible responses (default response unchanged in shape aside from the new null-valued fields; limit=3 populated history correctly with the one existing run).
**Files Modified**: src/backtest.py, src/data_store.py, src/pipeline.py, src/api.py, tests/test_backtest.py, tests/test_data_store.py, tests/test_pipeline.py, tests/test_api.py
**Context**: Code Generation for outcome-tracking feature (analytics-backtest + api-service units).

---

## Code Generation - Approval / Outcome-Tracking Feature Complete
**Timestamp**: 2026-08-07T02:10:00Z
**User Input**: "Continue to Next Stage"
**AI Response**: Approval recorded. Outcome-tracking feature (추천 결과 적중 판별 및 학습 반영) marked complete -- existing Build and Test instruction docs left as-is (not requested to update); user can ask for a refresh covering the new schema/endpoint if needed later.
**Context**: AI-DLC outcome-tracking feature request complete.

---

## New Request - Docker Smoke Test Documentation
**Timestamp**: 2026-08-07T03:00:00Z
**User Input**: "Using AI-DLC docker-compose 로 실행하고 build 했을 때 8000 포트로 뜨게 되어있는데 테스트는 어떻게해 readme에 없는데."
**AI Response**: Intent analysis: clear, simple, low-risk documentation gap -- README's existing `## 테스트` section only covers local `pytest` (code-level tests), nothing documents how to verify the running Docker container on port 8000 actually works. No genuine requirements ambiguity (Minimal Depth per requirements-analysis.md Step 3), so proceeded directly without a clarifying-questions file. Added a "실행 확인 (스모크 테스트)" subsection under the Docker section: `docker-compose ps` (healthcheck status), curl for /health, /recommendations, /recommendations?limit=3, POST /run, and `docker-compose logs -f`. Live-verified every documented command against a real `docker-compose up -d --build` -> confirmed `(healthy)` status, all curl commands returned the documented responses, `docker-compose logs` showed the requests, then `docker-compose down` cleaned up. Did not live-test POST /run this time (already verified working in this session and in original Build and Test -- avoided an unnecessary real Upbit/Binance API call).
**Files Modified**: README.md
**Context**: Docker smoke-test documentation follow-up request.

---

## New Request - Binance/Upbit 거래소별 추천 5개씩 포함
**Timestamp**: 2026-08-10T00:00:00Z
**User Input**: "Using AI-DLC 추천 리스트를 바이낸스, 업비트 기준 각각 5개씩 포함될 수 있도록 추가해주고, 바이낸스 거래량 최상위 20개로 추천 5개 찾아줘."
**AI Response**: Read src/market_selector.py, src/scorer.py, src/pipeline.py, src/data_store.py, src/binance_client.py, src/upbit_client.py, src/features.py, src/notifier.py, src/api.py, src/config.py to understand current state. Confirmed: recommendation candidates today come ONLY from Upbit (MarketSelector, top 20 by 24h trade value, BTC/ETH excluded); Binance is used solely as a market-regime reference (BTC/ETH 4h candles) and has never contributed recommendation candidates; only 4h Binance candles are collected (no 1h, needed for the golden-cross signal). `data_store.py` already separates candle storage by `source` ("upbit"/"binance"), so the existing signal/backtest algorithm (`compute_ichimoku`, `golden_cross_event`, `compute_signal_stats`) is fully source-agnostic and reusable without changes. Two genuine ambiguities identified with real consequences: (1) whether Binance's raw top-20-by-volume would be dominated by meaningless stablecoin/leveraged-token pairs, (2) how to handle an exchange returning fewer than 5 qualifying coins. Asked via AskUserQuestion (adapted from the project's file-based Q&A mechanism to this interactive session) rather than writing a question file and pausing indefinitely. Answers: (1) exclude stablecoin/leveraged pairs from the Binance top-20, (2) include only as many as pass the existing 4% threshold (no forced fill). Generated requirements.md (FR-B1..FR-B7, NFR-B1..B3).
**Context**: Requirements Analysis for Binance/Upbit balanced-recommendation follow-up request.

---

## Functional Design - Unit 1 (data-pipeline) + Unit 2 (analytics-backtest) + Unit 3 (api-service)
**Timestamp**: 2026-08-10T00:10:00Z
**User Input**: (proceeding per answered requirements)
**AI Response**: Extended existing per-unit docs in-place:
- Unit 1 business-rules.md: BR8 (Binance top-20 candidate filter -- USDT pairs, BTC/ETH excluded, stablecoin bases and UP/DOWN/BULL/BEAR-suffixed leveraged tokens excluded) and BR9 (1h+4h candle collection for Binance candidates, mirrors BR2-BR7 exactly, source="binance"). domain-entities.md: noted `TickerInfo` is reused as-is for Binance (no new entity).
- Unit 2 business-rules.md: BR13 (`generate_recommendations` takes `source` as a parameter and reuses BR1-BR9 unchanged; BTC/ETH regime stays a single global Binance-based gate, not per-exchange) and BR14 (cap each exchange's already-sorted list to `recommendations_per_exchange`, default 5, then concatenate upbit-group + binance-group -- no forced fill below threshold). domain-entities.md: added `source` field to `Recommendation`.
- Unit 3 business-rules.md: BR11 (expose `source` on `POST /run`/`GET /recommendations` responses and in notification lines as `[source] market: ...`). domain-entities.md: added nullable `source` column to `recommendations` table with the same ALTER-TABLE migration pattern as the outcome-tracking columns; NULL legacy rows interpreted as "upbit" (factually correct, matches NFR-B2).
NFR Requirements/NFR Design skipped (reuses existing SQLite/FastAPI/APScheduler stack, no new infra/tech-stack decisions).
**Context**: Functional Design for Binance/Upbit balanced-recommendation feature, all 3 units in one pass (small, tightly-coupled change).

---

## Code Generation - Unit 1 + Unit 2 + Unit 3
**Timestamp**: 2026-08-10T00:30:00Z
**User Input**: (proceeding per functional design)
**AI Response**: Modified in-place (brownfield):
- `src/data_store.py`: moved `TickerInfo` here from `upbit_client.py` (now shared by both clients); added `source` to the existing outcome-columns ALTER-TABLE migration list; `RecommendationRecord`/`save_run`/`get_pending_evaluations`/`_row_to_recommendation_record` all source-aware (NULL/missing -> "upbit" default, both in SQL and via `getattr` for duck-typed recommendation objects).
- `src/upbit_client.py`: imports `TickerInfo` from `data_store` instead of defining it locally.
- `src/binance_client.py`: added `get_tickers_by_volume()` (public `/api/v3/ticker/24hr`, filtered to USDT-quoted symbols only -- mixing quote currencies into one volume ranking would be meaningless).
- `src/market_selector.py`: added `BinanceMarketSelector` (BR8) with stablecoin-base and leverage-suffix exclusion, mirroring `MarketSelector`'s BTC/ETH exclusion pattern.
- `src/scorer.py`: `Recommendation` gained `source` (default "upbit"); `generate_recommendations` now takes `source` as an explicit parameter and threads it into `data_store.get_candles` -- no other algorithm change (BR13).
- `src/pipeline.py`: added `_collect_and_store_binance_candidate` (1h+4h collection mirroring `_collect_and_store`'s bootstrap/incremental/failure-isolation exactly); `run_recommendation_pipeline` now runs both market selectors, collects both candidate sets, calls `generate_recommendations` once per exchange, caps each to `settings.recommendations_per_exchange` (default 5) and concatenates (BR14); `evaluate_pending_outcomes` updated for the 3-tuple `(market, run_time, source)` so post-hoc evaluation reads candles from the correct exchange.
- `src/notifier.py`: message lines now prefixed `[source]`.
- `src/api.py`: `RecommendationOut` gained `source`; `GET /recommendations` and `POST /run` both expose it.
- `src/config.py` / `config/settings.yaml`: added `recommendations_per_exchange: int = 5`.
Updated/added tests across `test_market_selector.py`, `test_binance_client.py`, `test_scorer.py`, `test_pipeline.py`, `test_data_store.py`, `test_api.py`, `test_notifier.py` (existing `FakeRecommendation`/`RecommendationRecord` fixtures given a `source` field, defaulted so pre-existing assertions stay valid unchanged). Full suite: 106/106 passed (up from 91).
Live-verified against the REAL pre-existing `data/coin_recommender.db` (backed up to the session scratchpad first): confirmed via `PRAGMA table_info` that the `source` column was added cleanly (additive migration, no data loss, all pre-existing counts intact afterward: 5 pipeline_runs, 137542 upbit_candles, 42044+ binance_candles). Booted the real server, confirmed `GET /health` and `GET /recommendations?limit=3` still return correct backward-compatible data from the migrated DB, then triggered a REAL `POST /run` against live Upbit/Binance APIs (no mocks) -- it selected exactly 20 Binance candidates (verified none were stablecoin/leveraged pairs), bootstrapped 1h+4h candles for all 20 (1000 candles each, no errors/warnings in server logs), completed in ~41s with `regime_bullish=true`, and returned `recommendations=[]` (a legitimate result -- no coin's signal cleared the 4% expected-return threshold at test time, consistent with prior live runs in this project's history, not a bug). Server stopped cleanly afterward.
**Files Modified**: src/data_store.py, src/upbit_client.py, src/binance_client.py, src/market_selector.py, src/scorer.py, src/pipeline.py, src/notifier.py, src/api.py, src/config.py, config/settings.yaml, tests/test_market_selector.py, tests/test_binance_client.py, tests/test_scorer.py, tests/test_pipeline.py, tests/test_data_store.py, tests/test_api.py, tests/test_notifier.py
**Context**: Code Generation for Binance/Upbit balanced-recommendation feature (all 3 units).

---

## Code Generation - Complete
**Timestamp**: 2026-08-10T00:45:00Z
**User Input**: N/A (feature delivered per approved requirements, live-verified end-to-end)
**AI Response**: Binance/Upbit 거래소별 추천 5개씩 포함 기능 구현 완료. 기존 Build and Test 문서(build-instructions.md 등)는 갱신 요청이 없어 그대로 둠 -- 신규 설정값(`recommendations_per_exchange`)/API 필드(`source`) 반영이 필요하면 별도 요청 시 갱신 가능.
**Context**: AI-DLC Binance/Upbit balanced-recommendation feature request complete.

---

## New Request - 추천이 계속 안 나오는 원인 진단
**Timestamp**: 2026-08-10T06:10:00Z
**User Input**: "지금 이더랑 비트가 상승채널에 온게 아닌가. 계속 추천 코인이 없네"
**AI Response**: Treated as a defect suspicion and investigated with real data rather than speculating. Wrote read-only diagnostic scripts against the live DB (scratchpad only, no repo files). Findings: (1) the user was RIGHT -- the BTC/ETH regime gate passes (BTC 65,049 and ETH 1,919 both above a bullish cloud on the latest closed 4h bar; last 5 pipeline_runs all regime_bullish=1), so the regime was never the blocker; (2) the service is healthy -- docker container up 49min and healthy, hourly scheduler running, and all 40 current candidates (20 upbit + 20 binance) had candles 12 minutes old (the stale markets seen at first glance were simply coins that had dropped out of the top-20, which is correct behaviour, not a collection failure); (3) the real bottleneck is Unit 2 BR4's "golden cross on the EXACT latest bar" -- 0 of 40 fresh candidates satisfied it, because coins cross on average once per ~30 bars so the chance of landing on the latest bar is ~3% per coin. Ran a 30-day (720-hour) historical simulation: the current logic would have produced a recommendation in only 7 of 720 hours (1.0%) = one opportunity every ~103 hours. Hit DB lock contention mid-analysis (the live container was writing) and switched to an sqlite backup-API snapshot so the running production container was never disturbed.
**Context**: Diagnostic investigation, no code changed yet. Confirmed not-a-bug; converted into a tuning decision.

---

## Requirements Analysis - 빈도 개선 방향 결정 (사용자 1차 선택을 실측으로 반박)
**Timestamp**: 2026-08-10T06:25:00Z
**User Input**: (AskUserQuestion round 1) "기대수익률 임계값 낮춤" + "최근 3봉"
**AI Response**: Did NOT implement the stated choice, because measurement contradicted it -- per the project's behavioural rules ("근거가 있으면 반박한다"). Threshold sweep on real data showed: 4%→3% changes nothing at all (identical qualifying coins and opportunities -- no coin sits in that band), 4%→2% buys 29h→34h of exposure but drops the real 4% hit rate 93%→85%, and even removing the filter entirely (0%) only reaches one opportunity per 28h while hit rate collapses 81%→40%. So the threshold was not a working lever. A window x threshold matrix then showed the opposite of the intuitive trade-off: widening the golden-cross window improves frequency AND hit rate simultaneously (because the 4h trend and regime filters are still evaluated at the entry bar, so extra bars act as confirmation and screen out immediately-failing breakouts). Also computed distinct opportunity clusters to avoid overstating the gain -- honest numbers are 7→10 independent opportunities per 30 days (not 7→29 hours, most of which is the same opportunity persisting), and 3봉 vs 6봉 give identical opportunity counts (10), so 3 bars is the efficient choice. Flagged that the 86%→80% hit-rate difference rests on 6/7 vs 8/10 samples and is not statistically meaningful. Presented all of this and re-asked.
**Context**: Requirements Analysis. Evidence-based pushback on the user's first answer before writing any code.

---

## Requirements Analysis - Approved / Code Generation - Unit 2 (analytics-backtest)
**Timestamp**: 2026-08-10T06:40:00Z
**User Input**: (AskUserQuestion round 2) "3봉 확대, 임계값 4% 유지 (추천)"
**AI Response**: Implemented surgically -- left the `golden_cross_event` primitive untouched and added `golden_cross_within(points_1h, i, lookback=GOLDEN_CROSS_LOOKBACK_BARS=3)` in `src/backtest.py`, then switched BOTH entry tests to it: `backtest._composite_signal` (backtest sampling) and `scorer._composite_signal_on_latest_bar` (live check). Keeping the two in step is essential -- samples are measured from the entry bar, so `expected_return` describes the very entry the recommendation offers; changing only one side would make the advertised number describe a different trade. Threshold left at 4% in both places, and documented that the 4% in `backtest.py` (hit_count / target_reached) is the product's success definition and is deliberately distinct from the recommendation filter. Documented the known trade-off rather than silently absorbing it: one crossover can now yield up to 3 overlapping, correlated samples, so `n` counts entry opportunities rather than distinct crossovers (observed live: KRW-KAITO n=7 → n=22); the hit_count/n ratio stays valid but `n` overstates independent evidence. Did not build dedup (not requested). Updated tests: added 4 golden_cross_within boundary tests and 3 live-signal window tests, and rewrote the one test that assumed single-bar sampling to assert the window behaviour explicitly (n=3, mean 2%, hit_count=1). Caught and fixed an off-by-one in my own first draft of the boundary tests (cross at bar 1 with lookback 3 stays valid through bar 3 and expires at bar 4, not bar 3). Full suite: 113/113 passing (up from 106).
**Verification**: Proved the change actually does something rather than just returning 0 -- on live data, coins passing the golden-cross stage went 0 → 3 (KRW-HOME, KRW-KAITO, RLUSDUSDT), all three then correctly rejected downstream by the 4h trend and 4% filters, confirming the quality gates still work. The n=7→22 inflation appeared exactly as predicted. Current-moment output is still 0 recommendations, which is consistent with the analysis (~72h between opportunities means any single instant is usually empty) and is not a failure. Rebuilt and restarted the running docker container so the live service picks up the change: `docker compose up -d --build` -> container reports (healthy), GET /health and GET /recommendations both correct.
**Files Modified**: src/backtest.py, src/scorer.py, tests/test_backtest.py, tests/test_scorer.py
**Context**: Code Generation for the recommendation-frequency tuning request.

---

## New Request - 추천 신뢰도 향상 (질문 2건 + 품질 요구)
**Timestamp**: 2026-08-10T06:45:00Z
**User Input**: "Using AI-DLC 신뢰도는 높아져야해. 표본이 많아져서 발생한 케이스야?? 4%랑 3%랑 표본 차이가 심해??"
**AI Response**: Answered both questions from real data before proposing anything. (Q1) Yes -- the sample growth was almost pure duplication: samples went 78 -> 238 (3.1x) while distinct crossovers went only 78 -> 83 (+6%), with per-coin duplication factors sitting almost exactly on 3.0x. So the previous change's real benefit was exposure time (7h -> 29h), not new opportunities, as originally reported. (Q2) The 4%-vs-3% equivalence is not a sample-size effect but a gap in the distribution: expected returns run 17.01% -> 13.95% -> 5.16% -> 4.69% and then jump straight to 2.77%, so no coin occupies the 3-4% band. Investigation surfaced two genuine defects the user had not asked about: (1) duplicated samples bias `expected_return` itself, because a crossover whose trend/regime held for 3 bars silently receives 3x the weight of one that held for a single bar -- this flipped KRW-ONDO from -0.88% to +2.32%; (2) Binance history was being collected at 1/4.5 of the configured depth -- `binance_client.py`'s `min(limit, _MAX_LIMIT)` silently truncates at Binance's 1000-candle-per-response cap with no pagination, so `backtest_lookback_days: 180` produced 1,007 bars (41 days) while Upbit (paginated internally by pyupbit) held 4,415 bars (184 days). Measured the frequency cost of each reliability option and noted the sequencing point that fixing history first makes a minimum-sample floor cheaper. All analysis ran against sqlite backup-API snapshots so the live container was never disturbed.
**Context**: Requirements Analysis for the reliability request. Two defects found during diagnosis.

---

## Requirements Analysis - Approved / Code Generation - Unit 1 + Unit 2
**Timestamp**: 2026-08-10T06:55:00Z
**User Input**: (AskUserQuestion) "버그 2건 + 최소 교차 3회 (추천)" / "업비트와 동일하게 180일 (추천)"
**AI Response**: Implemented all three:
- `src/binance_client.py`: added `get_klines_since()` -- paginates forward from a start time, drops the overlapping candle Binance re-sends at `startTime`, stops on a short page, with a 20-request runaway guard. Left the single-request `get_klines` untouched as the incremental primitive.
- `src/data_store.py`: added `get_first_candle_time()` -- the backfill decision must key off the EARLIEST stored candle, since the incremental path only moves forward and could never repair an already-truncated market.
- `src/pipeline.py`: merged `_collect_and_store_binance_candidate` into `_collect_and_store_binance` with a `timeframes` parameter (the two had become near-duplicates and both needed the identical fix, so sharing it avoids applying the same change twice), and added the backfill-or-incremental branch. Documented the accepted cost that coins listed more recently than the lookback window re-fetch their short history each run.
- `src/backtest.py`: added `_last_cross_bar()` as a dedup key and made `compute_signal_stats` take one sample per crossover; added `MIN_SIGNAL_SAMPLES = 3`. Noted in the docstring why crossovers can never be adjacent (a cross leaves tenkan above kijun, so the next bar fails the `prev.tenkan <= prev.kijun` leg), which is what makes the entry-bar-to-crossover mapping unambiguous.
- `src/scorer.py`: applied the `n >= MIN_SIGNAL_SAMPLES` evidence floor.
Tests: added pagination tests (patching `_MAX_LIMIT` small to keep fixtures readable), `get_first_candle_time` tests, backfill-vs-incremental branch tests, a two-distinct-crossovers test proving dedup does not over-collapse, and evidence-floor tests. Rewrote the previous window test, which had asserted n==3, to assert n==1 -- that expectation was correct before dedup and is now exactly what the fix changes. Suite: 123/123 passing (up from 113).
**Verification**: Ran the real backfill against a COPY of the production DB first: 1,007 bars (41 days) -> 4,320 bars (180 days) for 1h and 1,002 -> 1,080 for 4h, ~0.8s per symbol, and confirmed a second run takes the incremental path (no repeated backfill). Then measured the reliability outcome across all 20 Binance candidates: average distinct crossovers per Binance coin rose 3.5 -> 7.5, and the deeper history exposed false positives that the 41-day window had manufactured -- ZECUSDT flipped from +5.16% (5 crossovers) to -0.67% (15 crossovers) and KRW-WLD fell from +4.69% (1 crossover) to +2.17%. Qualifying coins went 4 -> 2 (EPICUSDT, BANKUSDT), with both removals being genuine false positives rather than lost opportunities. Finally deployed to the live service: `docker compose up -d --build` -> healthy, real `POST /run` completed in 50s including the one-time backfill, and the production DB now holds 4,320 bars for every current candidate plus 1,080 for BTC/ETH.
**Files Modified**: src/binance_client.py, src/data_store.py, src/pipeline.py, src/backtest.py, src/scorer.py, tests/test_binance_client.py, tests/test_data_store.py, tests/test_pipeline.py, tests/test_backtest.py, tests/test_scorer.py
**Context**: Code Generation for the reliability request (data-pipeline + analytics-backtest units).

---

## New Request - 진입 가이드 및 24시간 유효기간
**Timestamp**: 2026-08-10T07:05:00Z
**User Input**: "Using AI-DLC 하루에 4%, 3% 수익볼 코인 추천하는거라서, 하루 이상을 넘기면 안되 추천대상이. 진입 시점도 가이드에 포함해줘."
**AI Response**: Confirmed two gaps and found a third defect. (1) No validity window -- `GET /recommendations` calls `get_latest_run()` with no age check, so a stalled scheduler would serve a days-old run as the current recommendation. (2) No entry information anywhere in the API response or the notification. (3) NEW DEFECT: the live signal was being computed on the still-forming candle. Verified against both live exchanges at 07:01:50 -- pyupbit and Binance each returned a 07:00 bar holding roughly two minutes of data, and the code took it as the latest bar. That contradicted BR7's own wording ("가장 최근 마감된 1h 봉") AND `scheduler.py`'s stated purpose ("5 minutes past the hour (waits for the 1h candle to close)") -- the scheduler waited for the bar to close and the code then picked the next, unfinished one. Consequences: a golden cross could appear then vanish once the bar settled (false signals), the backtest sampled only settled bars so train and serve disagreed, and no reproducible entry price existed to publish -- which blocks the requested entry guide outright. Treated as an unambiguous bug (spec violation with no trade-off) rather than a choice.
**Context**: Requirements Analysis for the entry-guide / expiry request.

---

## Requirements Analysis - 손절가 실측 후 사용자 선택 재확인
**Timestamp**: 2026-08-10T07:12:00Z
**User Input**: (AskUserQuestion round 1) "목록을 비우고 사유 표시" / "진입 시각+기준가, 목표가(+4%), 청산 기한(+24시간), 손절가"
**AI Response**: Implemented everything except the stop-loss, which was measured first rather than assumed -- the backtest has no stop concept, so any number would have been invented. Pooled 184 historical samples: coins that reached +4% had a median drawdown of -1.89% versus -2.74% for those that did not, distributions that overlap almost entirely, so a stop cannot separate winners from losers. Simulating stops at 2/2.5/3/4/5/6% moved the mean return only between 0.24% and 0.46% against a 0.34% baseline -- noise, in a distribution whose worst sample is -56.77% -- while a 2% stop cut 47% of the trades that eventually reached target, because this strategy characteristically dips before running. Reported that the data supports no stop level and offered alternatives; user chose to replace it with the observed drawdown statistic.
**Context**: Requirements Analysis. Second evidence-based pushback on a user selection this session.

---

## Code Generation - Unit 1 + Unit 2 + Unit 3
**Timestamp**: 2026-08-10T07:20:00Z
**User Input**: (AskUserQuestion round 2) "낙폭 통계로 대체 (추천)"
**AI Response**: Implemented:
- `src/data_store.py`: added `close_time()` and `drop_unclosed()` (candle_time is the OPEN time on both exchanges, so a bar is usable only once `candle_time + timeframe <= now`); added `entry_time`/`entry_price`/`max_drawdown` columns via the existing ALTER TABLE migration and threaded them through `RecommendationRecord`/`save_run` with `getattr` defaults so duck-typed and legacy callers still work.
- `src/upbit_client.py`, `src/binance_client.py`: apply `drop_unclosed` at the return boundary, so the unfinished candle never enters the DB and every downstream consumer (signal, backtest, outcome evaluation) automatically sees settled data only.
- `src/backtest.py`: `SignalStats.max_drawdown` plus an optional `candles_1h` argument to `compute_signal_stats` -- IchimokuPoint carries no low, and raw candles are index-aligned with points so the same `i` addresses both. Optional keeps existing callers and tests valid.
- `src/scorer.py`: `Recommendation` gained `entry_time`/`entry_price`/`max_drawdown`, sourced from the same bar the backtest measures from.
- `src/api.py`: entry-guide fields on `RecommendationOut`, with `target_price` and `exit_deadline` DERIVED at response time rather than stored so they cannot drift from the rules; `expired` flag and `_is_expired` keyed off run_time (all recommendations in a run share an hour, and it also covers legacy rows without entry_time); `POST /run` reuses `_to_recommendation_out` instead of its own duplicated construction.
- `src/notifier.py`: entry guide lines, omitted entirely when entry data is absent rather than fabricated, and the drawdown labelled "손절 지시 아님, 참고용".
Tests: 4 existing API tests failed after the change because their fixtures used hardcoded 2024 dates and were now correctly expired -- that was the feature working, so they were re-anchored to `now` and dedicated expiry tests added (expired, just-under-the-window boundary, history preserved while current is emptied). Added `drop_unclosed` tests including the exactly-closed boundary and 4h timeframe, drawdown tests, entry-guide persistence round-trip, and a legacy-object test proving `save_run` still accepts recommendations lacking the new attributes. Suite: 136/136 passing (up from 123).
**Verification**: Confirmed against the live exchanges that the unfinished bar is now excluded (07:16:41 -> latest 1h is 06:00, latest 4h is 00:00, both settled). Deployed and ran the real pipeline (50s, healthy). Because no coin currently has a signal, proved the entry guide end-to-end by replaying a real historical moment through the live code path: a thin store wrapper truncated candles at 2026-08-10T04:00Z (a moment that genuinely had a signal on binance/TUTUSDT) so `generate_recommendations` saw it as "now". Result -- entry 0.22939 at the 04:00 bar close, target 0.238566, deadline 04:00 next day, historical max drawdown -17.33%, with assertions that entry_time is a bar-close time and never in the future. Verified the production DB migration added all three columns.
**Files Modified**: src/data_store.py, src/upbit_client.py, src/binance_client.py, src/backtest.py, src/scorer.py, src/api.py, src/notifier.py, tests/test_data_store.py, tests/test_backtest.py, tests/test_api.py, tests/test_notifier.py
**Context**: Code Generation for the entry-guide / expiry request.

---

## Requirements Analysis + Code Generation - 백테스트 이력 1년 확대
**Timestamp**: 2026-08-11T07:55:00Z
**User Input**: "Using AI-DLC 180일 데이터 보다 더 많이 1년치 데이터 기준으로 처리될 수 있도록 변경해줘. 그리고 1년치 데이터는 저장하는거지?? 그래야 매번 호출 안하니까"
**AI Response**: 저장 여부 질문에 먼저 답하고(저장한다 — SQLite `data/coin_recommender.db` 33MB, 이력이 lookback 깊이에 도달한 마켓은 실행당 타임프레임당 1건의 증분 요청만), 설정값 변경만으로는 요구가 충족되지 않는다는 사실을 발견해 함께 수정했습니다. `_collect_and_store`(업비트)는 부트스트랩 여부를 `get_last_candle_time is None`(DB가 비었는가)으로만 판정하므로, 이미 180일치가 저장된 마켓은 증분 경로에 갇히고 증분은 앞으로만 진행합니다 — 즉 `backtest_lookback_days`만 365로 올리면 변경이 **바이낸스에만** 적용되고 업비트는 영원히 180일에 머무릅니다(2026-08-10에 고친 바이낸스 BR10과 동일한 구조적 결함이 업비트 쪽에 남아 있었음).
**Files Modified**:
- `config/settings.yaml`, `src/config.py`: `backtest_lookback_days` 180 → 365 (두 곳을 함께 — 어긋나면 컨테이너와 로컬 동작이 갈림)
- `src/pipeline.py`: `_bars_between()` 헬퍼 + `_collect_and_store`에 소급 백필 분기 추가. 바이낸스(BR10)와 달리 백필 범위를 **비어 있는 과거 구간만**(`to=first_time`)으로 한정 — 업비트는 요청당 200봉(바이낸스 1,000봉)이라 전체 재수집 비용이 5배이고, 상장이 lookback보다 최근인 코인은 이 분기를 매 실행 타므로(BR10의 "알려진 비용") lookback이 1년이 되면 해당 코인 수가 크게 늘어납니다. 과거 구간만 요청하면 그 상시 비용이 타임프레임당 1건으로 묶입니다
- `src/binance_client.py`: 폭주 방지 상한(20요청=20,000봉) 설명을 365일 기준(~8,760봉)으로 갱신
- `tests/test_pipeline.py`: 부트스트랩 전체 lookback 요청 / 얕은 이력 시 과거 구간 백필 / 이력 충분 시 증분만 — 3건 추가. 기존 실패 격리 테스트에 `get_first_candle_time` 스텁 보강
**Verification**: 운영 DB **사본**에 실제 업비트/바이낸스 API를 호출해 검증(운영 DB는 미변경). KRW-ADA 1시간봉 4,327→8,752봉(365일 도달), 4시간봉 1,081→2,190봉. 백필 1회 비용 30요청/4.4초, **재실행 시 2요청**으로 복귀 — 사용자 요구("매번 호출 안하니까") 충족 확인. 상장 1년 미만인 KRW-BLEND는 매 실행 4요청으로 제한(전체 재수집 설계였다면 26요청). 추가로 발견/검증한 의존성: 백테스트 표본은 BTC/ETH 4시간봉 레짐을 통과해야 채택되고 `as_of`는 기준 종목 이력 이전 시점에 None을 돌려주므로, 레짐 종목이 180일에 머무르면 새 이력이 **전부 기각**됩니다 — BTC/ETH를 365일로 백필하자 KRW-ADA 표본이 n=2 → n=13으로 실제 증가. 성능 실측 8,752봉 기준 코인당 0.60초(이치모쿠 0.56 + 스캔 0.04), 40개 코인 환산 24초로 매시 창 내. 테스트 139/139 통과(136에서 +3)
**Context**: Code Generation. 배포는 미수행 — 다음 파이프라인 실행 시 자동 백필되며 최초 1회만 약 2분 추가 소요.

---

## Requirements Analysis - 추천 확률 80% 요구 및 시그널 우위 검증
**Timestamp**: 2026-08-11T08:50:00Z
**User Input**: "3% 4% 오를 코인만 추천해주고, 오를 확률이 80% 이상 되어야해. 과거 데이터랑 비교하고 확률 참고해서, 어떤 차트 어떨때 오를지 정확도를 잘 산정해줘."
**AI Response**: 구현 전에 달성 가능성을 실측했고, **80%는 이 전략으로 달성 불가능**하다고 보고했습니다. 근거 4단계:
1. 기저율(395건, 366일x62마켓, 레짐 통과 진입만): 고가 +3% 터치 39.7%, +4% 터치 30.4%, 24h 종가 상승 38.7%, 평균 수익 -0.27%
2. 통계적 인증 불가: Wilson 95% 하한 >= 0.80 은 n=10에서 전승해도 72.2%로 미달, n=20 전승이 필요. 현재 코인당 표본은 3~13건 — "표본 3건 100%"를 다시 만드는 함정(이전에 KRW-WLD로 걸러낸 것과 동일)
3. 방향성 우위 부재: +4% 터치 30.4% vs -4% 터치 31.1%로 대칭. 자동 탐색이 찾은 최적 규칙(ATR>=1.74%)은 +4%를 51.7%로 올리지만 -4%도 60.0%로 더 올리고 평균 수익은 -0.27%->-1.19%로 악화 — 변동성 프록시일 뿐 방향성 아님
4. 현재 필터가 아무도 통과 못 시킴: train 구간 43개 코인 중 기대수익률>=4% & n>=3 통과 **0개**. 전체 이력 기준으로도 8,786시간 중 11시간(0.1%) — "14회 실행 0건"의 실제 원인
공정한 반론으로 표본 기간이 BTC -47.4%인 하락장임을 함께 보고(2026-07은 n=64에 평균 +2.19%로 양호).
**User Decision**: (AskUserQuestion) "시그널부터 다시 찾기 (추천)" / 판정 기준 "고가 터치 (추천)"
**Context**: Requirements Analysis. 세 번째 근거 기반 반박 — 요청 수치를 그대로 구현하지 않고 달성 가능성을 먼저 측정.

---

## Requirements Analysis - 시그널 탐색 결과 및 3년치 표본 확대
**Timestamp**: 2026-08-11T09:05:00Z
**User Input**: "Using AI-DLC 3년치 데이터로 표본을 늘려줘. 계산이나 수식에 사용하는 라이브러리들은 어떤걸 사용하고있어? python 라이브러리중에."
**AI Response**: 라이브러리 답변 — 지표 계산은 pandas-ta 0.4.71b0(`ta.ichimoku()`, src/features.py:41), DataFrame/벡터화는 pandas 3.0.5, NaN 판정은 표준 math. numpy 2.2.6은 pandas 의존성으로 설치만 되어 있고 src에서 직접 import 없음. **백테스트 계산(src/backtest.py)은 순수 Python 루프**로 pandas를 쓰지 않음 — NFR 문서의 "벡터화 필수, 행 단위 루프 금지"와 실제 구현이 불일치(성능은 실측상 문제없음). scipy/statsmodels/scikit-learn 미설치이며 Wilson 신뢰구간은 math.sqrt로 직접 구현.
직전 시그널 탐색 결과(9종 후보, 328,383봉, 57마켓, 기저 대비 시간분할 검증): **두 구간 모두에서 양(+)의 우위를 보인 시그널 0종**. 현재 전략은 train -7.5%p / test +15.7%p로 부호 반전. "레짐 의존인가 노이즈인가"를 BTC 추세 조건부로 검정한 결과 BTC 30일 상승 조건이 train -12.2%p(최악) / test +21.0%p(최고)로 역전 — 레짐 의존이 아니라 **노이즈**로 판정.
근본 한계가 방법이 아니라 표본(1년, BTC -47.4% 단일 레짐, 24h 창 중첩으로 실효 표본 더 작음)이라고 판단해 3년치 확대를 제안했고 사용자가 승인.
**Files Created (분석 전용, 운영 코드 아님)**: scratchpad의 prob_study.py, analyze.py, signal_search.py, regime_test.py, fetch_3y.py, analysis_3y.py. 3년치는 **별도 분석 DB**(analysis_3y.db)에 수집 — 운영 DB는 365일 유지(3년이면 크기 3배, 실행당 지표 계산 비용도 3배)
**발견**: `get_klines_since`의 폭주 방지 상한 20요청(=20,000봉)은 3년치 1시간봉(26,280봉)에 미달 — 운영 lookback을 3년으로 올릴 경우 조용히 잘림. 분석 스크립트는 max_requests=45로 직접 호출해 우회
**Context**: Requirements Analysis + 분석. 운영 코드 변경 없음.

---

## Requirements Analysis + Code Generation - 바이낸스 전용 재설계 (레짐 게이트 / 진입가·손절가·매도가)
**Timestamp**: 2026-08-11T10:30:00Z
**User Input**: "Using AI-DLC 강한 상승장, 반등 상승장 조합으로 바이낸스 기준으로 추천할떄 진입가, 손절가, 매도가 이렇게 처리될 수 있도록 만들어줘. 업비트 추천은 뺴줘. 24시간 이내로 터치 가능한 부분만"
**선행 대화 (같은 세션)**: 사용자의 "80% 확률" 요구와 "구름 뚫으면 상승장에선 가능하지 않나"라는 반박을 각각 실측으로 검증했습니다. (1) 80%는 1년/3년/5년 표본 모두에서 불가 — +3% 터치 상한이 전체 평균 46~48%, 강한 상승장 조건부로도 58.0%. Wilson 하한 80% 인증에는 n=20 전승이 필요. (2) 구름 돌파는 강한 상승장에서 48.0%로 무조건부 기저 50.0%보다 **낮음** — 가설 기각. (3) 다만 "상승장이 낫다"는 직관은 정확 — 기저가 하락장 39.0% -> 강한상승 50.0%로, 시그널 선택(최대 +8%p)보다 레짐(+11%p) 영향이 큼. (4) 기대수익률 4% 임계값이 실제 분포 최댓값(+2.68%)보다 높아 3%로 낮춰도 통과 0개 — 누적 추천 0건의 직접 원인.
**자체 발견 결함**: 분석 스크립트에서 bool Series를 `.shift(1)`하면 NaN이 생겨 object dtype이 되고, 거기에 `~`를 적용하면 -1/-2(둘 다 truthy)가 되어 "직전 봉이 구름 아래였다"는 조건이 무효화되고 있었습니다. 즉 "구름 돌파"가 실제로는 "구름 위 상태"를 측정했습니다. 조합(S1∩S8) 결과가 S8과 완전히 일치하는 것을 보고 발견했고, 수정 후 해당 시그널은 16/21 -> 13/21분기로 유의성이 사라져 앞선 보고를 정정했습니다. 결과가 이상해서가 아니라 우연한 수치 일치로 잡힌 버그라, 재실행 결과는 표본 수까지 같이 검토했습니다.
**User Decision**: (AskUserQuestion) 진입 조건 "C1 거래량돌파 ∩ 추세지속" / 손절 "-2% 적용, 확률도 그 기준". 손절의 실측 비용(목표달성 59.7%->40.7%, 매매의 53%가 손절 종료)을 제시한 뒤의 선택입니다.
**Files Modified**:
- `src/backtest.py`: 전면 교체. TARGET_RETURN=0.03 / STOP_LOSS=0.02, `simulate_trade`(봉 단위 목표-손절 경쟁, 동일봉 동시 충족은 손절 우선으로 보수 판정), `build_regime_series`/`regime_as_of`(BR20), `entry_signal`(BR19), `wilson_lower`. 골든크로스 계열(`golden_cross_event`/`golden_cross_within`/`_last_cross_bar`/`_composite_signal`/`_regime_bullish_at`)은 진입 조건 교체로 고아가 되어 제거. `evaluate_outcome`도 `simulate_trade`를 쓰도록 통일 — 추천 시 확률과 사후 성패가 다른 기준이면 적중률 기록이 무의미해짐
- `src/scorer.py`: 바이낸스 전용, 레짐 게이트 교체, 정렬 기준을 적중률이 아닌 Wilson 하한으로
- `src/pipeline.py`: 업비트 수집·추천 제거, 후보 4시간봉 수집 제거(새 진입 조건이 1시간봉만 사용), `PipelineRunResult.regime_bullish` -> `regime`
- `src/api.py`: `stop_price`/`hit_rate`/`hit_rate_lower` 추가. 적중률은 저장된 n/hit_count에서 유도하므로 **DB 마이그레이션 불필요**하고 과거 회차 행에도 같은 규칙이 적용됨
- `src/notifier.py`, `README.md`
- 테스트: `tests/test_backtest.py`/`tests/test_scorer.py` 전면 재작성, `tests/test_pipeline.py` 바이낸스 전용으로 재작성, `tests/test_api.py`/`tests/test_notifier.py` 기대값 갱신. 137/137 통과
**Verification**: (1) 운영 코드가 분석 스크립트를 재현하는지 대조 — 5년 DB 22마켓 898매매에서 목표달성 41.6%로 분석값(강한상승 40.7% / 반등 42.9%) 사이에 들어옴. (2) 현재 레짐이 None(하락장)이라 추천이 나오지 않으므로, 과거 강한상승 시점(2025-05-22T16:00Z)으로 캔들을 잘라 실전 코드 경로를 통과시킴 — WLDUSDT 진입 1.516 / 매도 1.56148 / 손절 1.48568 / 확률 40.9%(n=44, 18회 적중) / 청산기한 2025-05-23T17:00Z. 매도가=진입가x1.03, 손절가=진입가x0.98, 청산기한=진입+24h 3종 모두 assert 통과. (3) 성능: 5년 이력 기준 마켓당 1.6초(운영 365일이면 약 1/5)
**Context**: Code Generation. 배포 미수행 — 현재 레짐이 None이라 배포해도 추천 0건이며, 게이트가 열리는 시간은 5년 기준 약 19%(강한상승 11.5% + 반등 7.8%).

---

## Code Generation - 슬랙 알림 채널 추가
**Timestamp**: 2026-08-11T06:25:00Z
**User Input**: "슬랙으로 받을 수 있도록 해줘. 슬랙 키 값이나 필요하면 파라미터로 전달 받아서 실행되도록"
**AI Response**: Slack **Incoming Webhook** 방식으로 구현했습니다. Discord와 동일한 단일 URL POST이고 페이로드 키만 `content` -> `text`로 다르므로 기존 채널 패턴을 그대로 재사용했습니다. 봇 토큰 + `chat.postMessage` 방식(Telegram과 같은 토큰+대상 조합)은 채택하지 않았고, 필요하면 작은 변경이라고 안내했습니다 -- 요청받지 않은 두 방식 동시 지원은 넣지 않았습니다.
**Files Modified**:
- `src/notifier.py`: `send_notification`에 `slack_webhook_url` 파라미터 추가(기본값 None이라 기존 위치 인자 호출이 그대로 동작), `_send_slack` 추가, "설정된 채널 없음" 판정에 슬랙 포함
- `src/config.py`: `slack_webhook_url` (시크릿, .env 전용 — SECURITY-12)
- `src/pipeline.py`: `settings.slack_webhook_url` 전달
- `.env.example`: `SLACK_WEBHOOK_URL` 항목 및 발급 경로 안내 추가
- `README.md`: 시크릿 설명에 슬랙 반영
- `tests/test_notifier.py`: 슬랙 단독 발송/3채널 동시 발송/디스코드 실패 후 슬랙 계속 발송/슬랙 실패 시 예외 미전파/본문이 채널 간 동일 — 5건 추가
**Verification**: 페이로드 형태 확인 — POST `https://hooks.slack.com/services/...`, body `{"text": ...}` 단일 키. 본문이 Discord 발송분과 문자열 동일함을 테스트로 고정. 테스트 142/142 통과(137에서 +5). 실제 워크스페이스 발송은 웹훅 URL이 없어 미검증.
**Context**: Code Generation. `SLACK_WEBHOOK_URL`을 비워두면 슬랙으로는 보내지 않으며(에러 아님) 기존 채널 동작에는 영향 없음.

---

## Code Generation - 알림 형식 개선 (KST 표기 / 단락 분리 / 개수 표기)
**Timestamp**: 2026-08-11T06:40:00Z
**User Input**: "추천 결과에는 UTC 시간 말고 한국 시간으로 설정해주고, 추천 코인에 대한 결과도 단락 잘나눠서 정리해줘. 그리고 추천 코인 수도 상단에 표기해주고 (1) 이런식으로"
**AI Response**: 알림 메시지 형식만 변경했습니다.
- **KST 표기**: 실행 시각/진입 시각/청산 기한을 모두 `astimezone(KST)`로 변환. **저장(DB)과 API 응답은 UTC ISO 유지** -- 표시 형식과 저장 형식을 같이 바꾸면 과거 데이터 해석이 어긋나고, API는 오프셋이 붙은 ISO라 클라이언트가 자체 로케일로 렌더링하는 게 맞습니다.
- **단락 분리**: 추천 1건 = 빈 줄로 구분된 한 단락(`_recommendation_block`). 항목마다 `·` 불릿으로 확률/진입가/매도가/손절가/청산기한을 한 줄씩.
- **개수 및 번호**: 헤더에 `추천 코인 N개`, 각 종목 앞에 `(1)`, `(2)`. 0건일 때도 `추천 코인 0개`로 개수를 명시.
- 정렬용 공백에 의존하지 않는 형식으로 잡았습니다 -- 슬랙은 기본이 가변폭 글꼴이라 열 맞춤이 깨지고, 코드블록(```)으로 감싸면 Telegram이 parse_mode 없이 백틱을 그대로 노출합니다.
**Files Modified**: `src/notifier.py`(`_kst` 헬퍼, `_recommendation_block` 신설, `_format_message` 재작성), `tests/test_notifier.py`(기대값 KST/신형식으로 갱신 + 헤더 개수·KST 표기, 종목별 단락 분리, 0건 개수 표기 3건 추가)
**Verification**: 테스트 145/145 통과(142에서 +3). 실제 슬랙 워크스페이스로 추천 2건 예시를 발송해 렌더링 확인.
**Context**: Code Generation. 표시 계층만 변경이라 DB 마이그레이션·API 스키마 변경 없음.

---

## Code Generation - 추천 하한 45% 및 스테이블/금 토큰 제외
**Timestamp**: 2026-08-11T06:55:00Z
**User Input**: "매 시간 알림이 가도록은 설정유지할꺼야. 도달 확률 45% 이상인 것만 추려내주고, 거래량 상위 20개 중에 고르는 로직이 맞아?" / "스테이블이랑 금토큰은 제외하고 뽑아줘"
**AI Response**:
1. `MIN_HIT_RATE` 0.40 -> 0.45. 5년 표본 영향: 통과 코인 11개 -> 8개(탈락 NEARUSDT 43.5%, BICOUSDT 43.1%, TUTUSDT 42.9%). 0건 회차 알림 스킵은 사용자가 유지를 선택해 변경하지 않음.
2. 후보 선정 로직 검증 결과 **의도대로 동작하나 구멍 발견** — 스테이블 제외가 하드코딩 이름 목록이라 신규 페그 자산이 통과. 실측상 상위 20개 중 6개(30%)가 추천 후보가 될 수 없는 종목이었음: 스테이블/금 4종(USD1, RLUSD, XAUT, PAXG) + 이력 부족 4종(SPCXB, SNDKB, RLUSD, PAXG, 중복 제외 시 합계 6종).
**자체 정정**: 처음에는 24시간 변동폭 하한으로 자동 배제하는 방안(A)을 추천했으나, 실측 결과 **금 토큰이 정상 알트보다 더 움직여 분리 불가**임을 확인하고 철회했습니다 — XAUT 2.53% / PAXG 2.65% vs TRX 0.63% / DOGE 1.38% / BNB 1.55% / SOL 2.30%. 금이 걸리는 임계값은 메이저 알트를 함께 지웁니다. 명시 목록(B)이 맞는 선택이었고 그렇게 구현했습니다.
**Files Modified**:
- `src/backtest.py`: `MIN_HIT_RATE` 0.45
- `src/market_selector.py`: `_BINANCE_STABLECOIN_BASES`에 USD1/RLUSD/U/XUSD/EURI 추가(전부 현재가 ~1.00, 24시간 변동폭 0.02~0.29%로 페그 확인), `_BINANCE_COMMODITY_BASES = {XAUT, PAXG}` 신설. 변동성 방식을 쓰지 않은 이유를 docstring에 근거 수치와 함께 기록
- `tests/test_market_selector.py`: 신규 페그 자산 5종 제외, 금 토큰 제외, **조용한 날의 메이저(TRX/DOGE/BNB)를 지우지 않는다는 회귀 방지** 3건 추가
**Verification**: 테스트 148/148 통과(145에서 +3). 라이브 후보 재산출 결과 USD1/RLUSD/XAUT/PAXG가 모두 빠지고 그 자리를 DOGEUSDT, NEARUSDT, ADAUSDT, LINKUSDT가 채움 — 5년 표본에서 ADAUSDT 52.9%, DOGEUSDT 48.6%로 45% 하한을 통과하는 종목들입니다.
**알려진 유지보수 비용**: 이름 목록 방식이라 신규 페그 자산이 상위권에 올라오면 목록 갱신이 필요합니다. docstring에 명시했습니다.
**Context**: Code Generation.

---

## Code Generation - 가격 도달 감시 스케줄러 (5분 주기)
**Timestamp**: 2026-08-11T07:15:00Z
**User Input**: "추천 코인이 있을 경우에는 주기적으로 스케줄을 돌아 5분마다, 진입가에 도달했는지 상향가에 도달했는지 하안가에 도달했는지 확인하는 스케줄러 추가로 돌려줘."
**해석 명시**: "진입가 도달"은 추천 시점의 진입가가 그 순간 종가라 이미 도달 상태이므로, **"가격이 다시 진입가까지 내려와 지금 진입 가능해진 시점"**으로 해석했고 사용자에게 명시했습니다. 세 이벤트 모두 각각 1회만 알리며, 매도가/손절가 도달 시 해당 종목 감시를 종료합니다.
**Files Modified**:
- `src/data_store.py`: `entry_touched_at`/`target_hit_at`/`stop_hit_at` 컬럼(기존 ALTER TABLE 마이그레이션 재사용), `MonitoredRecommendation`, `get_monitorable_recommendations`, `mark_price_event`(NULL일 때만 UPDATE -- 기록 자체가 중복 알림 방지 장치)
- `src/monitor.py` (신규): `check_price_events`, `_events_for`. 1분봉 고가/저가로 판정하며 동일봉 동시 충족은 손절 우선(BR18과 같은 보수 판정)
- `src/notifier.py`: `_dispatch` 추출 후 `send_price_alert` 추가. 이벤트 0건이면 발송하지 않음(5분마다 "변화 없음"은 하루 288통)
- `src/pipeline.py`: `run_price_monitor`. 파이프라인 락을 공유하지 않음
- `src/scheduler.py`: `CronTrigger(minute="*/5")` 잡 추가
- `tests/test_monitor.py`(신규 12건), `tests/test_notifier.py`(+3), `tests/test_data_store.py`(+1)
**발견한 결함 (실호출 검증 중)**: `TIMEFRAME_HOURS`에 `1m`이 없어 `drop_unclosed`가 KeyError를 냈고, 감시 루프의 예외 처리에 먹혀 **이벤트 0건으로 조용히 넘어갔습니다.** MagicMock 클라이언트를 쓴 단위 테스트 12건은 전부 통과했고 실제 거래소 호출에서만 드러났습니다. 수정 후 회귀 방지 테스트 추가.
**Verification**: 테스트 164/164 통과. 운영 DB 사본에 실제 SOLUSDT 진입가(76.0800 @ 04:00Z)로 가상 추천을 넣고 실제 바이낸스 1분봉으로 감시 실행 -- entry 이벤트 1건 감지, 재실행 시 0건(중복 없음) 확인. 스케줄러 잡 2개 등록 확인(`cron[minute='5']`, `cron[minute='*/5']`). 슬랙으로 가격 알림 형식 예시 발송.
**Context**: Code Generation.

---

## Code Generation - 돌파 구간 4시간 + 구름 활용 방식 전면 검토
**Timestamp**: 2026-08-12T00:30:00Z
**User Input**: "비트랑 이더리움은 추세를 보기 위한 지표인거고, 실제로는 알트코인만 추천 대상이 될꺼야... 알트 코인 대상으로 3% ~ 4% 오를만한 코인만 추천되는거야. 지표는 구름대 뚫느냐 마느냐가 확률이 더 높아보이고 혹시 다른 케이스의 확률도 있다면 검토해주고, 그리고 진행해줘." / "돌파 기준은 그러면 24시간이 아니라. 4~8시간 정도가 적당해. 봉 하나가 더 생겨야 돌파기준인거지."
**AI Response**:
1. **변동성 비례 목표 제안을 철회**했습니다. 근거가 "비트는 3% 안 간다"였는데 BTC/ETH는 애초에 추천 대상이 아니므로 적용되지 않는 문제였습니다. 알트 대상 3~4% 유지가 맞습니다.
2. **구름 활용 방식 9종을 전면 검토**했고 현재 조건이 최고(+7.1p)였습니다. 구름 돌파 계열은 1h(+1.9p, 평균 -0.71%)·4h(-0.2p) 모두 열등했고, 4h 구름 위 조건을 추가해도 +7.1p → +5.6p로 나빠졌습니다. 후행스팬은 현재 조건에 이미 함축되어 결과가 완전히 동일했습니다. 사용자의 "구름 돌파가 확률이 높아 보인다"는 가설은 기각됐고, 현재 조건이 이미 구름을 "상태"로 쓰고 있음을 설명했습니다.
3. **돌파 구간 24 → 4시간** 적용. 실측상 4/6/8/12/24시간 모두 목표달성률 38.7~39.2%로 동일하고 매매 수만 935/919/911/898/874로 달라집니다 -- 돌파 구간은 사실상 무의미했고 실질 병목은 거래량 조건이었습니다. 품질 손실 없이 기회가 7% 많아 채택했습니다.
**중요 구현 판단**: 기존 구현은 돌파 구간과 거래량 평균 구간이 같은 상수를 써서, 돌파만 줄이면 거래량 조건이 "직전 4시간 평균의 2배"로 함께 약해집니다(미측정 영역). `VOLUME_BASELINE_BARS = 24`를 분리 신설했고, 두 구간이 독립임을 고정하는 테스트를 추가했습니다.
**Files Modified**: `src/backtest.py`(BREAKOUT_BARS=4, VOLUME_BASELINE_BARS 신설, entry_signal 이력 가드), `tests/test_backtest.py`(픽스처를 24봉 이력으로 갱신 + 분리 검증 테스트 1건), `aidlc-docs/.../analytics-backtest/functional-design/business-rules.md`(BR19 보강 + 기각한 구름 방식 표)
**Verification**: 테스트 166/166 통과. 운영 코드 재현 -- 5년 알트 기준 876매매 38.7% → **936매매 38.8%**(매매 +6.8%, 품질 동일). 45% 하한 통과 코인 6종(ADAUSDT 50.6% n=81, DOGEUSDT 46.3% n=108 등).
**Context**: Code Generation.

---

## 분석 - 사전 진입 / 되돌림 진입 검토 후 기각 (코드 변경 없음)
**Timestamp**: 2026-08-12T01:10:00Z
**User Input**: "매수 시점은 거래량 터지기 전 고가 달성하기 전 인거잖아. 이미 고가 넘어버린 이후에는 매수 할 이유가 없어. 사전에 이런걸 미리 예측해서 매수하려는거지." / (이후) "다시 재진행해줘. 다른 프로젝트 요청은 무시해."
**AI Response**: 지적이 타당함을 먼저 수치로 확인했습니다 -- 돌파봉은 자체로 중앙값 +1.91%, 4시간 전 대비 +3.76% 오른 자리에서 진입합니다. 그 뒤 두 방향을 모두 측정했고 **둘 다 현재 구조보다 나빴습니다**.
1. **사전 진입 5종**(변동성 수축, 거래량 고갈, 수축+고갈, 기준선 지지, 구름상단 근접): 목표달성률 30.1~35.4%로 현재(38.2%)보다 낮고, **"추세 유지 중이고 아직 돌파 안 함" 대조군(35.3%)에도 못 미침**. 돌파 직전 상태가 정보를 담고 있지 않다는 뜻.
2. **되돌림 진입 4종**: 승률은 38.8% → 40.9%로 오르지만 체결률이 46%로 떨어지고 **미체결 건의 69%가 그대로 목표 도달**. 성공 거래 수 363건 → 201건으로 절반 가까이 상실.
**해석**: 되돌아온다는 것 자체가 약한 돌파의 신호. 강한 돌파는 눌리지 않고 그냥 간다. 놓친 3.76%는 사전에 잡을 수 있었던 이익이 아니라 "돌파가 실제로 일어났다는 확인의 대가"다.
**Files Modified**: `aidlc-docs/.../analytics-backtest/functional-design/business-rules.md`(BR19 보강 -- 기각 근거표 2종). **운영 코드 변경 없음.**
**Context**: 분석. 같은 세션에서 다른 프로젝트(dreamline Jenkins 배포 실패) 문의가 있었으나 사용자가 무시하라고 지시해 중단했습니다 -- 해당 건은 메모리·디스크·SSH 모두 정상이며 로그상 배포 전 테스트 단계에서 실패한 것으로 보인다는 데까지만 진단했습니다.

---

## Code Generation - 반등 레짐에 장기 추세 조건 추가 (BR20-b)
**Timestamp**: 2026-08-12T02:00:00Z
**User Input**: "Using AI-DLC 짧게 열리는 구간 강한 상승장 두개다 캐치 가능한 형태가 좋아. 하락장 장기화에는 반등 해도 의미 없어서 애초에 시도조차 안하는게 맞는거같아." / "장기 하락장에는 상승할수 없는 구조야. 그 이유는 비트코인이랑 이더리움 영향을 받게되니까. 반등도 거짓반등인거고,"
**AI Response**: 처음 측정에서는 **가설과 정반대 결과**가 나와 사용자에게 그대로 보고했습니다 -- 장기 하락(90일 <= -20%) 구간의 반등이 47.8%로 가장 좋고, 그것을 빼면 38.8% → 37.3%로 나빠진다는 결과였습니다. 사용자가 구조적 근거(알트는 BTC/ETH에 끌려다님)로 재차 주장하자 **제 측정을 다시 검증했고 신뢰할 수 없음을 확인했습니다**:
- **생존 편향**: 장기 하락 반등 표본 234건 중 197건(84%)이 2022년 이전부터 존재한 9종목. 분석 유니버스가 "현재 거래대금 상위"라 2022년에 반등 후 사라진 알트는 데이터에 없음
- **사건 집중**: 234건이 5개 월에 84% 집중 -- 독립 관측이 아니라 사실상 5개 사건
편향 방향과 사용자 주장 방향이 정확히 일치하므로 측정치가 아니라 구조를 따랐습니다. **측정이 도메인 판단을 이기지 못한 사례**로 문서에 남겼습니다.
**Files Modified**:
- `src/backtest.py`: `REGIME_MA_BARS=1200`(200일), `REGIME_WARMUP_DAYS=210`, `_above_long_term_trend()` 신설. 반등 조건에만 적용하고 강한 상승장은 면제 -- 짧은 개방을 놓치지 않기 위함. 이동평균은 누적합으로 O(n) (매 봉 1,200개 합산은 O(n x 1200))
- `src/pipeline.py`: `_collect_and_store_binance`에 `lookback_days` 파라미터 추가, BTC만 `lookback + 210일` 깊게 수집
- `tests/test_backtest.py`: 장기 상승 추세 안의 반등은 인정 / 장기 하락 추세의 반등은 기각 / 이력 부족 시 기각 / **강한 상승장은 200일선 조건 면제** 4건으로 재작성
**Verification**: 테스트 169/169 통과. 5년 알트 22종 재현 -- 반등 레짐 봉 862 → 196(-77%), 개방 비율 19.8% → 13.3%, **개방 지속 중앙값 0.7 → 0.8일 유지, 최장 33.5일 불변**(강한 상승장 영향 없음 확인), 총 매매 936 → 645건, 목표달성 38.8% → 39.4%. 레짐 계산 0.13초.
**주의**: 목표달성률 +0.6%p는 같은 편향된 데이터에서 나온 값이라 개선 근거로 삼지 않았습니다. 채택 근거는 구조입니다.
**Context**: Code Generation.

---

## Code Generation - 표본 하한 안전장치 + lookback 5년 + 페이지 상한 수정
**Timestamp**: 2026-08-12T03:00:00Z
**User Input**: "이게 가장 보수적이면서 안정적인 상태 측정인거지?" / "안정장치 넣어줘" / "Using AI-DLC 5년 수집 범위를 좀 더 늘려도 좋을꺼같은데 10년으로."
**AI Response**:
1. **수수료를 처음 계산에 넣었고, 중요한 사실이 드러났습니다.** 전체 645매매 평균수익이 수수료 전 +0.136%인데 왕복 0.20%를 빼면 **-0.064%**입니다. 목표 +3%/손절 -2% 구조의 손익분기 적중률은 **41.2%**이고 전체 평균 39.4%는 그 아래입니다. 다만 45% 필터 통과 4종의 가중 적중률이 49.0%로 손익분기 대비 +7.8%p 여유가 있습니다 -- **45% 하한이 임의값이 아니라 수수료 손익분기선 역할**을 하고 있음을 확인했습니다.
2. **"안정적"이라고 단언하지 않았습니다.** 라이브 검증 0건, 생존 편향 잔존, 다중 검정, 슬리피지 미반영 네 가지를 명시했습니다.
3. **안전장치 요청에 대해 하한만 올리면 시스템이 멈춘다는 것을 먼저 측정해 보고했습니다.** 운영 DB 기준 레짐 개방이 2,196봉 중 6봉, 후보 20종의 표본 n이 최대 2로 하한 3조차 통과 불가였습니다.
4. **10년은 불가능함을 확인**했습니다 -- 바이낸스가 2017-07 출범이라 최장 BNB 8.8년이고, 현재 후보 20종 중 9년 이상 보유는 0종입니다. 5년 초과로 이득 보는 7종은 이미 n=52~79로 충분하고 표본이 부족한 신규 상장은 데이터가 없어, **5년이 실질적 최대치**임을 근거와 함께 제시했습니다.
**Files Modified**:
- `config/settings.yaml`, `src/config.py`: `backtest_lookback_days` 365 → 1825(5년)
- `src/backtest.py`: `MIN_SIGNAL_SAMPLES` 3 → 10
- `src/binance_client.py`: **결함 수정** -- `get_klines_since` 폭주 상한이 20페이지(20,000봉)여서 5년치 1시간봉(43,800봉=44페이지)이 예외 없이 2.3년에서 잘렸음. `_MAX_PAGES = 60`으로 상향
- `tests/`: 픽스처를 새 하한/lookback에 맞게 갱신, **폭주 상한이 설정된 lookback을 덮는지 검증하는 테스트 추가**(같은 결함 재발 방지)
**Verification**: 테스트 170/170 통과.
**배포 시 주의**: 다음 파이프라인 실행에서 5년치 백필이 일어나 최초 1회 약 10분 소요, DB 55MB → 약 200MB 예상.
**Context**: Code Generation.

---

## Diagnostic - 추천 0건 원인 분석 (코드 변경 없음)
**Timestamp**: 2026-08-13T05:00:00Z
**User Input**: "Using AI-DLC 현재 추천되는 코인이 아예 없는데 이게 맞는거야? 아니면 백테스트가 너무 빠듯하게 되서 추천이 1개도 없는거야? 최근에 4시간봉 돌파하는게 단한개도 없어??"
**AI Response**: 운영 DB 실측으로 3단계(레짐 게이트 → 진입 신호 → 통계 필터)를 분리 측정.
1. **돌파 신호는 마르지 않았다** -- 40개 마켓에서 최근 7일 146건, 30일 533건 발생. 돌파 부족이 원인이 아님.
2. **원인은 레짐 게이트(BR20)** -- `generate_recommendations`가 후보를 보기도 전에 `[]`를 반환. 마지막 개방 봉은 2026-05-05 20:00(약 100일 전), 2026년 전체 개방은 12,216봉 중 6봉(24시간).
3. **BTC 현재 상태**: 종가 63,647 / 200일선 69,815(-8.8%) / 30일 +1.72% / 저점대비 +1.79%. 강한상승(30일>+20%) 실패, 반등 3조건(30일<=0, 저점대비>+10%, 200일선 위) 모두 실패.
4. **regime_bullish=1이었던 8회 실행은 8/9~8/10** -- 커밋 4fc4964(200일선 반등 조건, 8/12 11:08) 이전. 반사실 측정: 200일선 조건 OFF 시 2026년 개방 68봉, ON 시 6봉.
5. **게이트가 열려도 즉시 추천되지는 않는다** -- 40종 중 n>=10 & 적중률>=45%를 통과하는 종목은 ADA(53.3%), AVAX(49.4%), BICO(48.1%) 3종뿐이고, 이 3종의 최근 7일 신호 합계가 4건이라 개방 시 대략 1~2일에 1건 수준.
**Files Modified**: 없음 (진단 전용, 임시 스크립트는 scratchpad에만 생성)
**Context**: 운영 진단 질의 응답.

---

## Diagnostic - 200일선 -> 100일선 반사실 측정 (코드 변경 없음)
**Timestamp**: 2026-08-13T05:40:00Z
**User Input**: "100일선으로 낮추면 어떤 문제가 생겨? 이점은 어떤게 생기고,"
**AI Response**: 완화가 아니라 **횡보 교환**임을 실측으로 확인. 제안(레버 2)을 스스로 기각.
1. **개방률 사실상 동일** -- MA200 1,902/12,216(15.6%) vs MA100 1,915/12,216(15.7%). 109봉 추가 / 96봉 제거.
2. **현재 문제를 전혀 해결 못함** -- 마지막 개방 봉 2026-05-05로 양쪽 동일. BTC는 MA100(-5.68%) 아래이기도 하고, 더 근본적으로 반등 선행조건 `30일<=0`이 오늘 +1.72%로 실패하므로 **이동평균을 어떻게 바꿔도 오늘은 안 열린다**.
3. **추가 109봉 중 87봉(80%)이 측정 불가** -- 2021-08-13(알트 1h 데이터 시작) 이전이며, 동시에 MA200 워밍업 미달 구간(BTC 4h가 2021-01-15 시작이라 1200봉=200일 후인 2021-08-03부터 판정 가능). 즉 추가분 대부분은 추세 판단 차이가 아니라 **워밍업 아티팩트**.
4. **그 87봉의 성격**: 2021-04-26~05-12 급락 반등. 구간 종료 후 30일 BTC 수익률 -31%~-43%. 200일선이 배제하려던 바로 그 거짓 반등.
5. **제거 96봉은 100% 측정 가능 구간** -- 2025-03, 2024-07, 2021-12의 정상 조정 후 반등. 평가 가능 순증감 **-74봉**.
6. **백테스트 재현(40종)**: 매매 912 -> 857건(-6%), 적중 39.4% -> 39.7%(노이즈), 수수료 후 -0.077% -> -0.062%(여전히 음수), 통과종목 3 -> 4종(LINK 43.3%->45.3%로 문턱 넘김, Wilson하한 33.7%). n>=10 종목 수는 14종으로 동일.
7. **연도별 반등 봉**: 2021 52->119, 2022 0->6, 2024 139->129, 2025 **57->7(-88%)**, 2026 0->0.
**결론**: MA100은 최근 연도에서 손해가 크고, 이득은 측정 불가 구간에 몰려 있으며, 당면 문제(게이트 폐쇄)를 해결하지 못함. 병목은 이동평균이 아니라 `ret_30d <= 0` 선행조건.
**Files Modified**: 없음 (진단 전용)
**Context**: 운영 진단 질의 응답.

---

## Functional Design - 횡보 레짐 신설 검토 후 기각 (BR20-c, 코드 변경 없음)
**Timestamp**: 2026-08-13T06:20:00Z
**User Input**: "2번으로 작업해줘."
**AI Response**: "먼저 측정 -> 기저 대비 우위 확인 -> 채택 여부 결정" 순서로 진행. **측정 전에 채택 기준 4개를 고정**(적중률 기저 초과 / 수수료 후 > 0 / 매매 100건 이상 / 5년 중 3년 이상 기저 우위)한 뒤 측정. 직전 MA100 검토에서 "완화인 줄 알았는데 아니었다"가 나온 뒤라 기준을 사후에 만들지 않기 위함.
1. **기저선 재측정** (바이낸스 40종, 5년, 신호 10,832건, 왕복수수료 0.20%): 무조건부 35.5%(5,765매매), strong_bull 40.0%(780), rebound 35.6%(132), 개방 전체 39.4%(912). **BR20-b 기록치 39.4%와 정확히 일치**해 재현 검증됨.
2. **횡보 후보 6종 전부 기준 ②에서 탈락** -- 수수료 후 양수인 후보 0개. 최선(F) -0.023%, 적중률 36.1%로 기저와 동일 수준. A/B/C는 기저보다 낮음. 연도 안정성도 1/5~3/5.
3. **세분표로 원인 확인**: -5%~+20% 대역 전체가 29~36%. 횡보는 정보가 없는 구간.
4. **급락 구간(30일<=-20%)이 유일하게 수수료 후 양수(+0.166%, 362매매, 41.2%)로 나왔으나 기각** -- BR20-b와 같은 함정. 상위 3개월이 56%, 2026-02 한 달이 30%(107건). 사건 20개 중 양수 10개(동전던지기). 최대 사건 제외 시 +0.046%로 붕괴. 2022-05 사건은 평균 +0.598%였으나 직후 BTC 30일 -34%.
5. **부수 발견 기록**: rebound 레짐(35.6%, 수수료후 -0.132%)은 기저(35.5%, -0.096%)와 구분되지 않음. 게이트 우위는 사실상 전부 strong_bull에서 나옴. BR20-b의 구조적 채택 근거는 유지하되 성적 기여가 없다는 사실을 문서에 명시.
**판정**: **채택 안 함.** 레짐 정의는 BR20/BR20-b 그대로 유지. 2026년 추천 0건은 게이트가 좁아서가 아니라 현재 시장에 우위가 없기 때문 -- 버려지는 10,314봉 어디를 잘라도 수수료를 넘는 구간이 없었음. **레짐을 건드리는 방향은 여기서 닫음.**
**Files Modified**:
- `aidlc-docs/construction/analytics-backtest/functional-design/business-rules.md`: BR20-c 절 추가 (기각 기록). `src/` 변경 없음.
**Context**: Functional Design (측정 기반 설계 검토).

---

## Diagnostic - 레버3(Wilson 하한 필터) 실측 후 제안 철회
**Timestamp**: 2026-08-13T06:50:00Z
**User Input**: "진행한다는게 어떤걸 진행한다는거야?"
**AI Response**: 제안 내용을 구체화하는 과정에서 **직전 답변의 과장을 발견하고 정정 + 제안 철회**.
1. **과장 정정**: "신규 상장 15종이 n=0이라 배제되는 문제를 Wilson 하한이 푼다"고 했으나 **틀렸음**. n=0은 표본이 없는 것이라 필터를 어떻게 바꿔도 구제 불가. Wilson 전환이 영향을 주는 집단은 `1<=n<=9`인 **9종뿐**.
2. **그 9종 전부 35% 문턱에서도 탈락** -- 최고가 ALLO/WLD의 20.7%(둘 다 n=1). 즉 현재 데이터에서 **완전한 no-op**.
3. **오히려 새 구멍이 생김**: MIN_SIGNAL_SAMPLES 제거 시 3/3(Wilson 43.8%), 4/4(51.0%), 5/5(56.6%)가 35% 문턱을 뚫음. 커밋 00e1d96이 막은 "얇은 표본" 구멍을 되엶.
4. **n>=10 집단 검증**: Wilson 35% 문턱은 ADA/AVAX/BICO로 현재와 동일한 3종. 40%면 ADA 1종. 즉 결과가 같거나 나빠짐.
**판정**: **레버3 철회.** 이득 0, 위험 신설. 현재 필터(n>=10 AND 원시>=45%) 유지가 맞음.
**부수 관찰(미실행, 제안만)**: `notifier._format_message`가 추천 0건일 때 "이번 회차 추천 없음"만 보냄. 레짐 상태를 담지 않아 사용자가 "게이트가 닫혀서 0건"인지 "신호가 없어서 0건"인지 구분 불가 -- 이번 대화의 최초 질문("이게 맞는거야?")이 발생한 직접 원인. `pipeline`은 `regime`을 이미 계산해 두고 알림에 넘기지 않음.
**Files Modified**: 없음
**Context**: 진단 및 제안 철회.

---

## Diagnostic - 게이트 개방 조건 산수 + '매집 패턴' 관측 가능성 (코드 변경 없음)
**Timestamp**: 2026-08-14T02:00:00Z
**User Input**: "언제쯤 열릴까 세력이 매집하고 있다던데 매집 패턴은 보여?"
**AI Response**: 예측은 하지 않고, (1) 게이트 개방에 필요한 가격은 산수로 계산, (2) '매집'은 관측 가능성부터 검증.
1. **반등 레짐은 향후 30일간 구조적으로 성립 불가** -- `30일수익률<=0`(가격 <= 30일전 종가)과 `200일선 위`(가격 > 200일선)를 동시에 요구하는데, 30일전 종가(63,491~65,400)가 200일선(69,714, 하루 -116씩 하락)보다 **낮다**. 두 조건을 만족하는 가격이 존재하지 않음. 9/13까지 계산해도 ref 63,491 < MA 66,237로 계속 불가능.
2. **따라서 향후 30일 개방 경로는 강한 상승장 하나뿐** -- BTC 75,388(최소 문턱, 9/1경) ~ 79,867 필요. 현재 63,491 대비 **+18.7% ~ +25.8%**.
3. **'세력 매집'은 이 데이터로 관측 불가** -- 보유 데이터는 바이낸스 OHLCV뿐. 호가창/체결주체, 온체인 지갑, 거래소 입출금, 미결제약정, 대량거래 식별 전부 없음. '세력'이라는 주체가 데이터에 존재하지 않음.
4. **OHLCV 대리지표는 매집의 반대를 가리킴** -- 30일 고저폭 7.4%(이례적 수축), **거래량비 0.78x(22% 감소)**, OBV 30일 -3,632 / 90일 -86,330(둘 다 음수). 가격 횡보 + 거래량 감소 + OBV 하락 = 관심 이탈 쪽.
5. **'매집=횡보+거래량 증가' 전제를 과거로 시험** -- 200일선 아래에서 거래량비 >=1.0x인 94봉의 이후 30일: 상승 40%, 중앙값 **-12.30%**. >=1.1x(49봉)는 상승 14%, 중앙값 -12.99%. 무조건부 기저(상승 52%, 중앙값 +0.64%)보다 나쁨. **단 월 3개/상위3=100%로 사실상 3개 사건이라 결론 못 냄** -- 자체 기준(BR20-c ③④) 적용해 "전제를 지지하는 증거 없음"까지만 기록하고 반대 주장도 하지 않음.
6. **현재와 가장 가까운 과거 10구간은 정확히 갈림** -- 2022-12~2023-10 4건은 이후 30일 +4~+31%, 2025-12~2026-05 6건은 -1~-30%. **같은 패턴, 정반대 결과.** 패턴 자체는 방향 정보를 담지 않음.
7. **기존 기각 기록과 일치** -- BR19 사전진입 검토에서 거래량고갈 30.8%, 변동성수축 30.1%, 수축+거래량고갈 33.6%가 모두 대조군 35.3% 이하로 이미 기각된 바 있음(표본 229~417로 이번보다 큼).
**Files Modified**: 없음
**Context**: 운영 진단 질의 응답. 예측 요청에는 산수로만 답하고 시세 전망은 하지 않음.

---

## Diagnostic - "200일선은 이미 오르고 난 뒤 진입" 가설 검증 (코드 변경 없음)
**Timestamp**: 2026-08-14T03:10:00Z
**User Input**: "100일선 기준으로 맞추면 뭐가 문제가되? 200일선은 이미 상승하고 난 뒤 진입하는 시점같아보여."
**AI Response**: 직전 MA100 검토(2026-08-13)는 **결과**(적중률/순수익)만 봤고 **진입 지연**은 안 봤으므로, 지연만 따로 측정. 가설은 기각됐으나 사용자 직관이 겨냥한 실제 지점은 따로 있었음.
1. **가설과 반대 결과 -- MA200이 가장 이르다** (직전 30일 저점 기준 중앙값):

| 정의 | 에피소드 | 저점 후 경과 | 저점 대비 상승 |
|---|---|---|---|
| MA200 반등 | 31 | **9.0일** | **10.7%** |
| MA100 반등 | 35 | 11.3일 | 12.1% |
| MA50 반등 | 54 | 16.0일 | 18.4% |
| 조건 없음 | 145 | 9.8일 | 11.0% |

이동평균을 짧게 할수록 **더 늦게, 더 오른 뒤** 진입한다. 이동평균이 병목이 아니라 `저점대비 > +10%`가 병목이기 때문 -- 짧은 선은 더 깊은 하락의 반등을 추가로 통과시키고, 그것들이 자격을 얻으려면 더 많이 올라야 한다.
2. **개방 직후 BTC 수익률 (움직임이 끝났는지 직접 검증)**: 무조건부 기저 이후30일 +0.45%/상승52%. MA200 반등 **+5.48%/54%**, MA100 반등 -1.52%/47%, MA50 반등 -0.93%/42%, 조건없음 -0.03%/50%. **선을 짧게 할수록 단조 악화.** MA200 반등의 이후 7일이 -2.56%인 것은 오히려 **약세 구간에 일찍 들어간다**는 뜻으로, "이미 오른 뒤"와 반대.
3. **자체 기준 적용 -- 단, 증명된 것은 아님**: MA200 반등 248봉/31에피소드, **에피소드 단위 양수 16/31(52%)**, 상위3개월 47%. 평균 +8.11%는 2024-02(+54.33%), 2021-10(+28.53%) 소수가 견인. BR20-c 기준 ③④를 적용하면 "MA200이 좋다"고 주장할 수 없음. **말할 수 있는 것은 "지연 가설을 지지하는 증거가 없고, 어떤 단축안도 개선을 못 냈다"까지.**
4. **사용자 직관이 실제로 겨냥한 지점은 강한상승** -- 저점 후 **27.7일, +25.7% 오른 뒤** 진입. 이건 문자 그대로 "이미 상승하고 난 뒤"가 맞음. 다만 이후30일 +2.16%/상승59%로 기저(+0.45%/52%) 우위이고, 매매 단위로는 적중 40.0%(780매매) vs 기저 35.5%로 시스템 우위의 대부분을 담당. 에피소드 단위로는 27/68(40%)이고 최대 에피소드 제외 시 평균이 음수(-0.95%)가 되나, 이는 BTC 30일 방향 측정이고 시스템은 24시간 단기 모멘텀을 취하므로 직접 모순은 아님.
5. **구조적 개방 가능성은 단축으로 안 풀림** -- 30일전 종가 > 이동평균인 봉 비율: MA200 51.9%, MA100 51.0%, MA50 48.5%. 오늘 기준으로도 MA100(67,333)은 여전히 30일전 종가(65,044)보다 높아 **반등 성립 불가**. 유일하게 오늘 열리는 것은 MA50(63,407)인데 **MA50이 이후 수익률 최악(상승 42%)**.
**판정**: MA100/MA50 전환 모두 채택 안 함. 근거는 "지연이 개선되지 않고(오히려 악화), 개방 가능성도 안 넓어지며, 오늘 열리는 유일한 안이 성적 최악"이라는 세 가지.
**Files Modified**: 없음
**Context**: 운영 진단 질의 응답 (사용자 가설 검증).

---
## Follow-up Request (2026-08-18): BTC/ETH 강세장 구분 문구 출력
**Timestamp**: 2026-08-18T00:05:50Z
**User Input**: "Using AI-DLC BTC, ETH 강세장일 경우 문구도 바꿔서 출력될 수 있도록 해줘. 일, 주, 월 데이터 분석해서, 상승 모멘텀 기준으로 약상승장 강상승장 구분될 수 있도록"
**AI Response**: 워크스페이스 탐지(브라운필드, 기존 aidlc-state.md 존재 -> 재개) 후 Requirements Analysis 진입. 요청에 해석이 갈리는 지점이 4개 있어 `requirement-verification-questions.md`로 질문 생성.
**Context**: Workspace Detection (resume) -> Requirements Analysis (Standard depth) 시작. 코드 변경 없음.

---
## Requirements Analysis + Code Generation — BTC/ETH 강세장 문구 (BR23)
**Timestamp**: 2026-08-18T00:25:00Z
**User Input**: "일 주 30일, 월, 년 데이터 전체 기준으로 분석해. 일 주 30일만으로는 부족해보여."
**AI Response**: 질문 4개 중 구간 정의(Q2)에 대한 직접 지시로 받아 5구간(1일/7일/30일/90일/365일)으로 확정. 나머지 3개는 아래와 같이 판단해 진행하고 근거를 명시.
1. **적용 범위 = 표시 전용** — 요청이 "문구도 바꿔서 출력"이었고, 게이트(BR20)를 바꾸면 발표 중인 적중률(BR21 45% 문턱)이 측정 조건과 어긋남. 코드도 `src/market_phase.py`로 분리해 매매 경로와 물리적으로 떼어놓음.
2. **BTC+ETH 결합 = 합의 요구** — 요청 문구가 "BTC, ETH 강세장일 경우"였으므로 두 자산 합의를 요구.
3. **임계값 = 실측 후 확정** — 강상승 30일 +20%(BR20의 STRONG_BULL_30D와 같은 값이나 상수는 분리) + 90일/365일 양수, 약상승 30일 양수 + 5구간 중 3개 이상 양수.
**측정 결과** (BTC/ETH 4시간봉, 2022-01-21~2026-08-17, 10,019봉):
- 빈도 강상승장 4% / 약상승장 26% / 상승장 아님 70%
- 그 시점 BTC 30일 중앙값 +36.0% / +12.1% / -3.5% (단조 분리 확인)
- 게이트 교차: 강상승장 416봉 **전부** `strong_bull` 안 — 문구와 게이트가 모순된 사례 없음
- **예측력은 주장하지 않음**: 강상승장 15개 에피소드 중 이후30일 양수 9개(60%), 그중 6개가 2024-11 편중 → BR20-c 기준 ③④에 걸림. 문구는 현재 상태 설명으로만 사용.
**구현 중 자기 기각 1건**: 느슨한 결합 규칙("하나라도 상승이면 약상승장")을 먼저 구현하고 실 데이터로 확인한 결과 BTC 비상승(365일 -45.0%, 90일 -16.0%) + ETH 약상승 상황에서 헤드라인이 "약상승장"으로 나와 본문과 모순됨. 합의 요구 규칙으로 교체하고 빈도표도 재측정.
**Files Modified**:
- `src/market_phase.py` (신규), `src/scorer.py`, `src/pipeline.py`, `src/notifier.py`, `src/api.py`
- `tests/test_market_phase.py` (신규 17개), `tests/test_notifier.py` (7개 추가) — 전체 194/194 통과
- `aidlc-docs/construction/analytics-backtest/functional-design/business-rules.md` (BR23), `aidlc-docs/construction/api-service/functional-design/business-rules.md` (BR23), `aidlc-docs/aidlc-state.md`
**Live 검증**: 실 DB 백업 후 ETHUSDT 4h 12,209봉 신규 수집 → 실제 발송 메시지 렌더링 확인 → `GET /recommendations` 200 + `market_phase` 정상 → `GET /health` 200.
**Context**: Requirements Analysis + Functional Design + Code Generation (표시 전용 변경이라 NFR 단계는 해당 없음).

---
## Diagnostic Request (2026-08-18): 이력 5년 초과 시 확률이 올라가는가
**Timestamp**: 2026-08-18T01:20:00Z
**User Input**: "Using AI-DLC 5년치 데이터보다 좀 더 많으면 예측하는데 더 높은 확률로 나오나"
**AI Response**: 추측하지 않고 실측으로 답하기로 함. `backtest_lookback_days=1825`를 늘렸을 때 (1) 표본 n, (2) 표시되는 적중률, (3) 실제 추천 통과 종목이 어떻게 변하는지 측정 예정.
**Context**: Requirements Analysis (진단 질의). 측정 결과에 따라 코드 변경 여부 판단.

---
## Diagnostic Request (2026-08-18): 반감기 4년 주기 / 4·8·12년 정렬
**Timestamp**: 2026-08-18T01:45:00Z
**User Input**: "Using AI-DLC 4년마다 반감기가 도달해서 가격 상승을 하는 시기가 있어. 이 부분도 고려해서 처리하는게 맞을꺼같은데. 그러면 4년 8년 12년 데이터가 의미 있지 않나. 더 많은 데이터가 있는게 더 좋을꺼아니야 정확도 면에서는"
**AI Response**: 직전 답변의 프레이밍을 정정. "확률 숫자가 올라가나"를 측정했고 "정확도가 올라가나"는 측정하지 않았음 -- 후자는 사용자 말이 맞음(표본 증가 = 신뢰구간 축소). 반감기 주기 가설은 별도 측정.
**Context**: Requirements Analysis (진단 질의, 사용자 가설 검증).

---
## Diagnostic Result (2026-08-18): 이력 확대 / 반감기 주기 실측 (코드 변경 없음)
**Timestamp**: 2026-08-18T02:10:00Z
**AI Response**: 바이낸스 최대 이력(BTC 4h 9.0년 19,712봉, 5년 초과 이력 보유 8종 1h 51,196~76,848봉)을 신규 수집해 측정.

**1. 프레이밍 정정** -- 직전 답변은 "확률 숫자가 올라가나"만 측정했고 "정확도"는 측정하지 않았음. 정확도는 사용자 말이 맞음:

| lookback | 표본 n | 적중률 | 95% 신뢰구간 | 반폭 |
|---|---|---|---|---|
| 3년 | 329 | 38.0% | 32.7~43.2% | ±5.2%p |
| 5년 | 539 | 38.2% | 34.1~42.3% | ±4.1%p |
| 7년 | 1,032 | 36.1% | 33.2~39.1% | ±2.9%p |
| 9년 | 1,153 | 36.9% | 34.2~39.7% | ±2.8%p |

표본 2.1배, 신뢰구간 반폭 ±4.1%p -> ±2.8%p로 축소. **추정은 실제로 정확해진다.** 다만 정확해진 값이 36~37%이고 이는 5년 추정(38.2%)보다 낮다.

**2. 후보 20종 중 5년 초과 이력 보유는 8종뿐** -- 나머지 12종(TUT/GPS/ACE/ALLO/XPL/SNDKB/SPCXB/BFUSD/SUI/WLD/PORTAL/SKHYB)은 상장 자체가 0.1~3.3년 전. lookback을 늘려도 이들에겐 아무 변화가 없다.

**3. 옛 데이터는 지금과 다른 시장이 아니다(안정적)** -- 연도별 적중률 2019~2025: 44/35/35/38/35/41%, 표준편차 3.6%. 최근5년 38.3% vs 5년이전 35.7%. 즉 옛 데이터는 노이즈가 아니라 **약간 나쁜 진짜 표본**이고, 합치면 평균이 내려간다.

**4. 45% 문턱이 실제 능력보다 높다** -- 7년/9년에서 통과 종목 0. 5년에서 유일 통과한 DOGE도 44.8%(n=87, Wilson 하한 34.8%)로 문턱 초과를 신뢰구간이 보증하지 못하며, 전체 이력에선 39.4%로 내려감.

**5. 워크포워드(선택 편향 측정)** -- 'Y년 이전' 성적으로 고른 종목의 'Y년' 실제 성적: 38.9%(n=36) vs 전체 평균 36.2%(n=756). 필터의 실제 우위는 **+2.6%p뿐**이고, 표시되는 45% 대비 **-6.1%p**. 2022~2025년은 선택 종목이 아예 없었음.

**6. 반감기 4년 주기 가설** -- 매매 적중률: 0~1년차 33.6% / 1~2년차 40.8% / 2~3년차 40.8% / 3~4년차 36.8%. **반감기 직후가 오히려 최저.** BTC 30일 수익률로는 0~1년차 +5.61%(63%)로 반대 방향.
**재현성이 핵심 결함**: 같은 연차를 두 사이클이 재현하지 못함 -- 0~1년차 2020사이클 +13.6%(67%) vs 2024사이클 +3.0%(59%), 1~2년차 -4.6%(40%) vs +0.4%(52%)로 **부호가 다름**. 바이낸스 이력에 완전한 사이클은 **2개뿐**이라 BR20-c 기준 ③④를 적용하면 주기 패턴을 주장할 수 없다.

**7. 12년치는 존재하지 않음** -- 바이낸스 BTCUSDT 최초봉 2017-08-17, 가용 9.0년. 8년은 8종에 한해 가능.

**판정**: 코드 변경 없음. lookback 확대는 정확도 면에서 타당하나 45% 문턱과 **결합된 결정**이라(확대 시 추천 0건) 사용자 결정 사항으로 제시.
**Files Modified**: 없음 (`src/` 무변경)
**Context**: 진단 질의 응답 + 사용자 가설(반감기 주기) 검증.

---
## Code Generation (2026-08-18): lookback 5년 → 12년 확대
**Timestamp**: 2026-08-18T02:40:00Z
**User Input**: "우선 이력을 확대하려고해. 최대 12년까지 데이터로 확대해볼꺼야. 문턱은 그 다음 변경이야."
**AI Response**: lookback만 확대하고 문턱(MIN_HIT_RATE)은 손대지 않음.
**변경 파일**: `config/settings.yaml`(backtest_lookback_days 1825→4380), `src/config.py`(기본값 동일 변경), `src/binance_client.py`(`_MAX_PAGES` 60→130), `src/backtest.py`(MIN_SIGNAL_SAMPLES 근거 주석의 낡은 수치 갱신), `tests/test_binance_client.py`(가드 테스트 독스트링), `aidlc-docs` 3종.
**핵심 발견 — 조용한 절단 재발 직전이었음**: `_MAX_PAGES=60`은 1시간봉 60,000봉(6.8년)까지만 받는다. 12년은 106페이지가 필요하므로 설정만 바꿨다면 **예외 없이 6.8년에서 잘려** 12년으로 돌고 있다고 착각했을 것. 2026-08-12에도 동일 성격의 결함(20페이지→2.3년 절단)이 있었음. 기존 가드 테스트가 설정값에서 필요 페이지를 유도해 이를 잡아냄.
**Live 검증**: 실 DB 백업(155MB) 후 백필 136초. 8종 확장(BNB 43,940→76,848, XRP→72,581, TRX→71,666, LINK→66,439, ZEC→64,915, DOGE→62,373, SOL→52,731, NEAR→51,196), **12종은 상장이 0.1~3.3년 전이라 무변화**. BTC/ETH 4h 12,246→19,712봉(2017-08-17까지). 봉 수가 별도 수집분과 정확히 일치해 절단 없음 확인. 풀스캔 47.3초(시간당 1회), DB 155MB→180MB. 194/194 통과.
**2026-08-12 결정 뒤집음**: 당시 "5년이 실질적 최대"라며 기각했으나 근거가 "표본이 충분한가"에 한정됐고 "추정이 정확한가"를 재지 않았음. 비용 추정치도 과대했음(추정 70초/400MB vs 실측 47.3초/180MB).
**반감기 가설 기각**: 사이클 연차별 매매 적중률 0~1년차 33.6%(최저)/1~2년차 40.8%/2~3년차 40.8%/3~4년차 36.8%. BTC 가격은 반감기 직후 상승(+5.61%/63%)하나 24시간 매매 적중률은 반대. 두 사이클이 서로 재현 안 됨(1~2년차 -4.6%/40% vs +0.4%/52%, 부호 반대). 완전 사이클 2개뿐 -> BR20-c ③④ 적용, 사이클 정렬 미도입.
**미착수**: MIN_HIT_RATE 45% 조정은 사용자가 다음 건으로 지시.
**Context**: Code Generation (설정 확대 + 절단 결함 예방).

---
## Code Generation (2026-08-18): lookback 12년 → 16년 재측정 + 수집 결함 수정
**Timestamp**: 2026-08-18T03:20:00Z
**User Input**: "Using AI-DLC 16년치 데이터 기준으로 재측정해줘. 최대 16년"
**AI Response**: 16년으로 설정하고 재측정. **데이터는 1봉도 늘지 않음** -- 바이낸스 개장이 2017-07이라 9.0년이 절대 상한. 통합 n=1,277 / 적중률 37.0% / 신뢰구간 반폭 ±2.6%p로 12년과 동일.
**측정 중 발견한 회귀 (직전 12년 변경이 만든 결함)**: `_collect_and_store_binance`의 백필 조건 `first_time > target_start`가 lookback 확대 후 항상 참이 되어 **모든 종목을 매 실행마다 전량 재수집**했다(실측 시간당 약 600요청/136초). 거래소에 없는 과거를 영원히 다시 받는 구조. "거래소의 최초봉을 이미 보유했는가"를 1요청으로 확인하는 조건 추가로 수정 -- **136초 → 9초**(BNB 9→0초, XRP 29→0초). 판단 실패 시 백필로 폴백.
**Files Modified**: `config/settings.yaml`(4380→5840), `src/config.py`, `src/binance_client.py`(`_MAX_PAGES` 130→150), `src/pipeline.py`(`_is_exchange_earliest` 신설 + 백필 조건), `tests/test_pipeline.py`(기존 1건 갱신, 회귀 2건 추가), `aidlc-docs` 3종. 196/196 통과.
**Context**: Code Generation. 16년은 "앞으로 7년간 재조정 불필요"라는 의미 외에 실질 효과 없음을 명시.

---
## Correction (2026-08-18): "완전한 사이클 2개" 기록 정정
**Timestamp**: 2026-08-18T03:50:00Z
**User Input**: "반감기 사이클이 4년마다인데 16년치 데이터인데 2개뿐이라고? 말이 안되.."
**AI Response**: 사용자 지적이 맞고 **두 가지 오류를 정정**.
1. **"16년치 데이터"가 아니다** -- 5840일은 `backtest_lookback_days` **설정 상한**이고 실제 확보 데이터는 **9.0년**(2017-08-17 ~ 2026-08-18)이다. 바이낸스 개장이 2017-07이라 그 이전은 거래소에 존재하지 않는다. 직전 보고에서 "16년 설정"과 "9.0년 실제"를 나란히 적었으나 표 제목이 "16년"이라 오해를 유발했음.
2. **완전한 사이클은 2개가 아니라 1개다** -- 이전 측정 스크립트가 센 것은 "데이터 구간 안에 포함된 반감기 *사건* 수"(2020-05, 2024-04)였고 완전한 *사이클* 수가 아니었다. 실제: 2012~2016 사이클 0%, 2016~2020 사이클 71%(앞부분 잘림), 2020~2024 사이클 100%(유일한 완전 사이클), 2024~2028 사이클 58%(진행 중, 1.7년 남음). **즉 근거는 내가 보고했던 것보다 더 약했다.**
**가용성 확인(코드 변경 없음)**: 4개 사이클을 채우려면 2012-11 이전 데이터가 필요하며 바이낸스에는 앞 4.7년이 비어 있다. lookback 설정으로는 해결 불가(거래소 개장이 물리적 상한). 대안 소스 실측: **Bitstamp BTC/USD 일봉이 2011-09-13부터 = 14.9년 = 끝까지 관측되는 사이클 3개 + 진행 중 1개**. CoinGecko는 무료 키 없이 401.
**Files Modified**: `aidlc-docs/construction/analytics-backtest/functional-design/business-rules.md`(사이클 커버리지 표 추가 + 정정), `aidlc-docs/aidlc-state.md`(정정). `src/` 무변경.
**Context**: 기록 정정. 반감기 별도 기능의 데이터 소스 결정으로 이어짐.

---
## Follow-up Request (2026-08-18): 장기/단기 추천 2트랙 분리
**Timestamp**: 2026-08-18T04:00:00Z
**User Input**: "Using AI-DLC 장기 상승은 반감기에 도달했을 떄 발생하는거고, 단기 상승은 하락장에서 약세장 진행할때 발생하는거니까.  장기 상승할때 추천하는 기능이랑 단기 상승 추천 기능이랑 별도로 구성해주고, 단기 상승은 24시간 이내 3% ~ 4% 상승을 타겟으로 하고 장기 상승장에서는 5~10%정도 상승할 정도로 추천하는걸 구분해서 두 종류로 추천하는게 좋을꺼같은데."
**AI Response**: 설계 전에 요청에 담긴 **검증 가능한 전제 2개**를 먼저 측정하기로 함 -- (1) 장기 상승이 반감기 구간에 몰리는가, (2) 단기 상승이 하락장 반등 구간에서 발생하는가. 사이클 3개 확보를 위해 Bitstamp 일봉(2011-09~)을 측정용으로 수집. 코드 변경 전 단계.
**Context**: Requirements Analysis (신규 기능, 사용자 전제 검증 우선).

---
## Diagnostic Result (2026-08-18): 2트랙 전제 검증 (코드 변경 없음)
**Timestamp**: 2026-08-18T04:30:00Z
**AI Response**: Bitstamp BTC/USD 일봉 14.9년(5,454봉, 2011-09-13~) 측정용 수집. **완전 사이클 3개** 확보로 이전 9년(완전 1개)에서는 불가능했던 재현성 검증 수행.

**전제 1 (장기 상승 = 반감기) -- 확인됨, 3개 사이클 전부에서 재현**
목표 +10% / 손절 -10% / 보유 90일:

| 사이클 연차 | 표본 | 도달률 | Wilson 하한 |
|---|---|---|---|
| 0~1년차 | 1,464 | **65.5%** | 63.0% |
| 1~2년차 | 1,460 | 45.1% | 42.6% |
| 2~3년차 | 1,125 | 56.5% | 53.6% |
| 3~4년차 | 873 | 61.2% | 57.9% |
| 전체 기저 | 4,922 | 56.6% | - |

재현성(목표 +10%): 0~1년차가 2012사이클 66% / 2016사이클 74% / 2020사이클 72%로 **3/3 모두 기저 초과**. 1~2년차는 34%/53%/39%로 **3/3 모두 기저 미만**. 목표 +5%에서도 0~1년차 75.0% vs 기저 69.0%로 같은 방향. **BR20-c 기준 ③④를 통과하는 첫 사이클 근거** -- 단, 3개 사이클은 여전히 적고 BTC 단독 측정이다.

**전제 2 (단기 상승 = 하락장 반등) -- 반대로 나옴**
현행 게이트의 두 레짐 분리 측정(목표 +3%, 손절 -2%):
- 강한 상승장: **37.5%** (n=1,118)
- 반등(하락장 내): **33.7%** (n=175)

단기 상승도 **강한 상승장에서 더 잘 발생**한다. "하락장 반등에서 단기 상승이 발생"은 지지되지 않음.
목표 상향도 불리: +3% 37.0% -> +4% **29.8%** (전체 기준). 사용자 언급 범위 3~4% 중 **3%가 우월**.

**타이밍 제약 (설계 전 필수 고지)**: 현재 2026-08-18은 직전 반감기(2024-04-20) 기준 **2.33년 경과 = 2~3년차**. "0~1년차만" 게이트는 다음 반감기(2028-04 추정)까지 **1.7년간 추천 0건**. "3~4년차 포함"이면 2027-04부터(0.7년 후) 열림.

**미검증 영역**: 사이클 우위는 **BTC 일봉 단독** 측정이다. 알트는 바이낸스 이력이 2017년 이후라 사이클 3개 검증이 불가능하므로, 장기 트랙을 알트로 확장하는 것은 근거 없음.
**Files Modified**: 없음 (`src/` 무변경)
**Context**: Requirements Analysis -- 사용자 전제 2개 중 1개 확인, 1개 반증. 설계 결정 사용자에게 제시.

---
## Follow-up Request (2026-08-18): 2트랙 게이트=BTC, 추천=알트 상위 10~15
**Timestamp**: 2026-08-18T04:50:00Z
**User Input**: "Using AI-DLC 장기 트랙 단기 트랙 감지는 btc 기준으로 하고, 그거에 따라서 알트 추천들이 있으면 좋을꺼같은데 거래량 상위 10~15개 사이에서 안전하게."
**AI Response**: 게이트=BTC / 추천=알트 구조는 기존 단기 시스템과 동일한 뼈대라 채택. 단 **발표 확률의 출처가 바뀐다** -- 사이클 우위 65.5%는 BTC 가격 기준이므로 알트 매매에 붙일 수 없음. 알트 기준 재측정 선행.
**Context**: Requirements Analysis. 설계 전 알트 레벨 측정.

---
## Diagnostic Result (2026-08-18): 알트 레벨 사이클 우위 측정
**Timestamp**: 2026-08-18T05:15:00Z
**AI Response**: 게이트=BTC / 추천=알트 구조에서 **발표할 확률은 알트 기준이어야** 하므로 재측정.

**1. 목표 +10%(사용자 요청 5~10% 범위)에서는 알트에 우위가 거의 없다**
목표 +10% / 손절 -10% / 보유 90일, 후보 20종:
- 0~1년차 53.3% / 1~2년차 49.2% / 2~3년차 50.5% / 3~4년차 54.2% / 기저 51.6%
- **0~1년차 우위 +1.7%p뿐** (BTC는 같은 조건에서 65.5% vs 56.6% = +8.9%p)
- 종목별로도 13종 중 7승 6패(TRX +12%p, ZEC +7%p vs ACE -7%p, WLD -8%p, GPS -35%p)로 일관성 없음

**2. 밴드를 변동성에 맞게 키우면 우위가 살아난다 (직전 결론 정정)**
"우위가 사라진다"는 +10% 밴드에 한정된 얘기였음:

| 밴드 | 알트 0~1년차 | 알트 기저 | 알트 우위 | BTC 우위(참고) |
|---|---|---|---|---|
| +10%/-10% | 53.3% | 51.6% | +1.7%p | +8.9%p |
| +20%/-20% | 59.3% | 52.9% | +6.4%p | +14.2%p |
| +30%/-30% | 59.3% | 49.7% | +9.6%p | +19.3%p |

즉 **알트로 장기 트랙을 하려면 목표가 +5~10%가 아니라 +20~30%여야 한다.** 사용자 요청 범위(5~10%)는 알트에서 우위가 나오지 않는 구간이다.

**3. 그러나 알트의 재현성은 약하다 -- 2020 사이클이 지배**
알트 데이터로 관측 가능한 0~1년차는 2개 사이클뿐:

| 밴드 | 2020 사이클 | 2024 사이클 |
|---|---|---|
| +20% | +21.8%p (74.7%) | **+4.4%p** (49.3%) |
| +30% | +31.8%p (78.5%) | **+4.3%p** (46.8%) |

방향은 2/2 일치하나 **크기가 5~7배 차이**. 통합 59.3%는 2020~2021 알트 불장이 끌어올린 값이고, 최근 사이클 기준으로는 49.3%다. BR20-c 기준으로 **"0~1년차가 유리한 방향"까지만 말할 수 있고 크기는 발표할 수 없다.**

**4. "거래량 상위 10~15"와 "안전하게"가 충돌한다**
현재 상위10에 SNDKB(상장 2026-06, 1,620봉)·XPL·GPS·ALLO·TUT 등 신규 상장이 포함되고, 검증된 TRX(12위)·DOGE(17위)·NEAR(18위)·LINK(19위)는 밖으로 밀린다. **신규 상장이 거래량을 끌어올리기 때문.** 상위 N을 좁히는 것만으로는 안전해지지 않으며, 최소 이력/표본 요건을 함께 걸어야 한다(현행 MIN_SIGNAL_SAMPLES와 같은 방향).

**설계 판정 (사용자 결정 대기)**: 장기 트랙의 근거 강도가 대상별로 다르다 -- BTC는 3사이클 3/3 재현으로 견고, 알트는 2사이클 방향만 일치. 코드 변경 없음.
**Files Modified**: 없음
**Context**: Requirements Analysis. 사용자 요청(알트 5~10%)과 측정 결과의 충돌을 제시.

---
## Follow-up Request (2026-08-18): 장기 트랙에 알트 포함 + 모멘텀 지속 가설
**Timestamp**: 2026-08-18T05:30:00Z
**User Input**: "장기 트랙에서는 한번 크게 오른놈이 더 잘가니까. 거래량 높아진거 알트 넣을꺼야 장기트랙에도"
**AI Response**: 알트 포함 결정 수용. 함께 제시된 가설("이미 크게 오른 종목이 더 간다" + "거래량 증가")은 검증 가능하므로 측정. 이 필터가 실제로 작동하면 직전 측정의 약점(2024 사이클 +4.4%p, 재현성 부족)이 해소될 수 있음.
**Context**: Requirements Analysis. 진입 필터 가설 검증.

---
## Diagnostic Result (2026-08-18): 모멘텀 지속 반증 / 거래량 확인
**Timestamp**: 2026-08-18T05:50:00Z
**AI Response**: 목표 +20%/-20%, 보유 90일, 알트 후보 20종, 표본 25,797건. 사이클마다 시장 상황이 달라 절대 수치는 비교 불가하므로 **각 사이클 자체 기저 대비 우위**로 판정(2020 사이클 기저 58.0%, 2024 사이클 기저 46.7%).

**가설 1 "한번 크게 오른 놈이 더 간다" -- 반증됨**
- 직전 30일 수익률별 도달률: -20%미만 47.0% / -20~0% 54.4% / 0~+20% **55.3%** / +20~50% 52.6% / +50~100% 56.1% / +100%초과 51.7%. **단조 증가하지 않음**
- (사이클 무관) 30일>+20% 필터: 2020 **-2.5%p** / 2024 **-1.5%p** -- 두 사이클 모두 기저보다 나쁨
- 0~1년차 + 30일>+20%: 2020 +6.7%p / 2024 -0.5%p -- 불일치
- **이미 오른 종목을 고르는 것은 이 조건에서 손해다.**

**가설 2 "거래량 높아진 것" -- 확인됨, 두 사이클 일관**
거래량비(최근 7일 평균 / 그 이전 23일 평균)별: 0.8배미만 49.2% / 0.8~1.0 54.0% / 1.0~1.3 54.5% / **1.3~2.0 58.0%** / 2.0초과 53.7% (과열 구간은 다시 하락).

| 조건 | 표본 | 2020 우위 | 2024 우위 | 판정 |
|---|---|---|---|---|
| 0~1년차만 | 7,027 | +17.1%p | +2.3%p | 불일치 |
| (사이클 무관) 거래량>1.3배 | 5,956 | +3.3%p | +3.9%p | 일관, 작음 |
| **0~1년차 + 거래량>1.3배** | 1,678 | **+13.0%p** | **+11.7%p** | **일관** |
| 0~1년차 + 거래량>1.5배 | 1,156 | +11.1%p | +14.4%p | 일관 |
| 0~1년차 + 30일>+20% + 거래량>1.3배 | 726 | +0.9%p | +14.1%p | 불일치 |

**핵심: 사이클과 거래량은 둘 다 있어야 한다.** 사이클만으로는 재현 안 되고(+17.1/+2.3), 거래량만으로는 우위가 작다(+3.3/+3.9). 결합하면 두 사이클에서 +12%p 내외로 일관. **모멘텀 조건을 추가하면 오히려 망가진다**(+0.9/+14.1).

**한계 명시**: 여전히 사이클 2개이고, 조건 9개를 시험해 고른 결과라 out-of-sample 검증이 아니다. 절대 수치는 사이클마다 다르므로(2020 71% vs 2024 58%) 발표 확률은 보수적으로 잡아야 한다.
**Files Modified**: 없음
**Context**: Requirements Analysis. 사용자 가설 1 반증 / 가설 2 채택. 장기 트랙 진입 조건의 측정 근거 확보.

---
## Follow-up Request (2026-08-18): 장기 트랙 4시간봉 + 구름 돌파
**Timestamp**: 2026-08-18T06:05:00Z
**User Input**: "Using AI-DLC 거래량 실리고, 4시간봉 단위로 추천되면 되지 않나. 크게 상승할놈은 구름대 뚫는놈이고,"
**AI Response**: 4시간봉 진입 + 구름 돌파 조건을 측정. "구름 위 유지"(기존 is_bullish)와 "구름을 뚫는 순간"(신규)은 다른 조건이므로 분리 측정.
**Context**: Requirements Analysis. 진입 조건 가설 검증.

---
## Diagnostic Result (2026-08-18): 4시간봉 진입 / 구름 조건 검증
**Timestamp**: 2026-08-18T06:25:00Z
**AI Response**: 4시간봉 진입으로 재측정(표본 154,734건, 일봉 진입 25,797건의 6배). 각 사이클 자체 기저 대비 우위로 판정.

**1. 4시간봉 진입 -- 채택.** 일봉 진입과 결과가 일치하고(0~1년차+거래량>1.3: 일봉 +13.0/+11.7 vs 4시간봉 +12.6/+10.7) 표본과 진입 기회가 크게 늘어난다.

**2. "구름대 뚫는 순간"(돌파) -- 기각.** 모든 목표에서 2024 사이클 우위가 사라진다:
- 목표 +20%: 2020 +13.8%p / 2024 **+2.8%p**
- 목표 +30%: 2020 +20.1%p / 2024 **+0.8%p**
- 목표 +50%: 2020 +38.0%p / 2024 **-0.9%p**
표본도 198건으로 얇다. 돌파 순간을 잡는 것은 재현되지 않는다.

**3. "구름 위 유지" -- 채택, 단 목표가 클 때만.** 사용자 직관의 방향은 맞았으나 조건이 "뚫는 순간"이 아니라 "구름 위에 있는 상태"다:

| 목표 | 거래량만 (2020/2024) | 구름위+거래량 (2020/2024) | 구름 조건의 효과 |
|---|---|---|---|
| +20% | +12.6% / +10.7% | +10.5% / +10.2% | 약간 해로움 |
| +30% | +20.8% / **+7.4%** | +19.6% / **+10.1%** | 개선 |
| +50% | +35.1% / **+6.4%** | +35.3% / **+12.0%** | 크게 개선 |

목표가 커질수록 구름 위 조건이 2024 사이클의 우위를 끌어올린다. "크게 상승할 놈"이라는 직관은 **큰 목표에서** 성립한다.

**권장 조합**: 0~1년차 + 구름 위 + 거래량>1.3배 + 목표 **+30%/-30%** + 보유 90일 + 4시간봉 진입.
도달률 2020 사이클 74% / 2024 사이클 54%(각 기저 54%/44% 대비 +19.6%p/+10.1%p). 발표 확률은 보수적으로 **54%**.

**한계**: 사이클 2개, 조건 다수 시험 후 선택이므로 out-of-sample 아님. 현재 2~3년차라 게이트는 닫혀 있음.
**Files Modified**: 없음
**Context**: Requirements Analysis. 사용자 가설 방향 확인 / 세부 조건 정정.

---
## Follow-up Request (2026-08-18): 장기 트랙 목표 +20%, 손절은 작게
**Timestamp**: 2026-08-18T06:40:00Z
**User Input**: "목표는 20%  장기 트랙에서는 목표를 크게 잡고 손절은 작게 잡아. 차트가 살짝 누르고 쭉 반등하기 떄문에."
**AI Response**: 목표 +20% 확정. 비대칭 손절은 측정으로 검증 -- 제시된 근거("살짝 누르고 반등")는 오히려 좁은 손절이 그 눌림에 걸린다는 반대 방향의 함의가 있으므로, (1) 최종 승자의 최대 눌림폭 분포, (2) 손절폭별 기대수익을 측정.
**Context**: Requirements Analysis. 적중률만이 아니라 기대수익으로 판정해야 하는 구간(비대칭 손익).

---
## Diagnostic Result (2026-08-18): 손절폭 측정 -- "손절 작게" 지시와 반대 결과
**Timestamp**: 2026-08-18T06:55:00Z
**AI Response**: 진입 조건 고정(0~1년차 + 구름위 + 거래량>1.3배, 4시간봉), 목표 +20% 고정, 손절폭만 변화. 표본 6,077건.

**1. 손절폭별 성적 -- 좁힐수록 기대수익 단조 감소**

| 손절 | 도달률 | 손절률 | 기대수익 | 2020 기대 | 2024 기대 |
|---|---|---|---|---|---|
| -5% | 26.6% | 73.4% | **1.66%** | 2.58% | 0.84% |
| -10% | 45.7% | 54.0% | 3.79% | 5.28% | 2.45% |
| -15% | 55.9% | 43.5% | 4.72% | 6.33% | 3.29% |
| -20% | 62.4% | 36.4% | 5.24% | 7.38% | 3.33% |
| -30% | 71.6% | 24.3% | **6.83%** | 10.29% | 3.75% |

**2. 이유 -- '살짝'이 살짝이 아니다.** 결국 +20%에 도달한 4,905건의 도달 전 최대 눌림:
중앙값 **8.4%**, p75 **18.7%**, p90 **31.8%**, p95 38.5%.

| 손절 설정 | 승자 중 먼저 잘려나가는 비율 |
|---|---|
| -5% | **67.1%** (3,289/4,905) |
| -10% | 43.3% (2,126/4,905) |
| -15% | 30.7% (1,505/4,905) |
| -20% | 22.7% (1,115/4,905) |
| -30% | 11.3% (553/4,905) |

"차트가 살짝 누르고 쭉 반등한다"는 관찰 자체는 맞다 -- 다만 그 '살짝'의 중앙값이 8.4%이고 4건 중 1건은 18.7% 넘게 눌린다. **손절 -5%는 최종 승자의 3분의 2를 먼저 잘라낸다.** 좁은 손절은 이 패턴을 이용하는 게 아니라 이 패턴에 걸린다.

**판정**: 목표 +20% 확정. 손절은 **-20%(대칭) 권장**, 사용자가 비대칭을 원하면 -15%가 타협점(기대수익 4.72%, -20% 대비 -10% 손실). -5%/-10%는 측정상 명확히 불리. 사용자 결정 대기.
**Files Modified**: 없음
**Context**: Requirements Analysis. 사용자 지시와 측정 결과가 충돌 -- 근거 제시 후 결정 요청.

---
## Requirements 확정 (2026-08-18): 장기 트랙 파라미터
**Timestamp**: 2026-08-18T07:10:00Z
**User Input**: "-10% 손절가를 잡아야겠다."
**AI Response**: 측정 결과(-10%는 -20% 대비 기대수익 3.79% vs 5.24%, 승자의 43.3%가 먼저 잘림)를 제시했고 사용자가 -10%로 재확인 -> **사용자 결정으로 확정하고 진행**.

**겹침 제거 후 최종 수치 (발표용)**: 지금까지 수치는 4시간봉마다 센 겹친 표본(6,077건)이었음. 단기 트랙 `compute_signal_stats`와 같은 규칙(보유 중 신규 진입 없음)을 적용하면:
- 독립 매매 **448건**, 목표 도달 **42.0%** (Wilson 하한 37.5%), 기대수익 **+2.63%**
- 2020 사이클 n=263 도달 44.5% 기대 +3.35% / 2024 사이클 n=185 도달 38.4% 기대 +1.61%
- **알림에 표시할 확률은 45.7%가 아니라 42.0%** (또는 종목별 값)

**예상 빗나감 정정**: 종목별 독립 표본이 얇아 종목별 확률 필터가 불가능할 것으로 예상했으나 **12종 모두 10건 이상**(ACE 13 ~ DOGE 74). 종목별 확률 산출이 가능하다. 종목별 도달률 26%(WLD) ~ 50%(SUI).

**적중률 문턱은 두지 않기로 제안**: 전체가 42.0%인데 단기 트랙의 45% 문턱을 그대로 적용하면 SUI/TRX/XRP/DOGE 4종만 남고, 이는 표본 13~74건에서 상위값을 고르는 것이라 선택 편향(단기 트랙 워크포워드에서 실측된 -6.1%p 괴리)을 그대로 재현할 위험이 크다. 표본 하한 10건 + Wilson 하한 정렬만 적용.
**Context**: Requirements Analysis 확정 -> Functional Design 진입.

---
## Follow-up Request (2026-08-18): 2~3년차에도 장기 트랙 개방
**Timestamp**: 2026-08-18T07:30:00Z
**User Input**: "2~3년차라도 장기 트랙 오픈해줘."
**AI Response**: 게이트를 넓히면 표시 확률이 연차별로 달라지므로, 확정 파라미터(+20%/-10%, 겹침 제거)로 연차별 재측정 후 설계 반영.
**Context**: Functional Design 변경 요청 -> 재측정.

---
## Code Generation (2026-08-18): BR24 장기 트랙 구현
**Timestamp**: 2026-08-18T07:50:00Z
**User Input**: "2~3년차라도 장기 트랙 오픈해줘." / "Using AI-DLC 완료 후 재빌드 해서 docker 구동시켜줘. 지금 돌고있는 docker 내리고"
**AI Response**: 개방 연차를 (0, 2)로 확정하고 장기 트랙 구현 후 도커 재기동.
**신규**: `src/long_track.py`(사이클 게이트/거래량비/진입조건/시뮬레이션/표본), `tests/test_long_track.py`(24건)
**변경**: `src/scorer.py`(`generate_long_recommendations`, track 필드), `src/pipeline.py`(장기 후보 4시간봉 수집 + 2트랙 실행), `src/data_store.py`(track 컬럼 + **PK를 (run_time, market)에서 (run_time, market, track)으로 재구성**), `src/notifier.py`(트랙별 섹션·규칙), `src/monitor.py`(트랙별 목표/손절/보유기간), `src/api.py`(track 필드 + 트랙별 목표가/손절가/기한), `src/config.py`·`config/settings.yaml`(`long_top_n_candidates: 15`)

**구현 중 발견·수정한 결함 1건 (중대)**: `simulate_long_trade`가 데이터 끝에서 잘라 **진행 중인 매매를 타임아웃으로 집계**했다. 단기 트랙 `simulate_trade`는 창이 안 차면 None을 돌려주는데 이를 따르지 않았다. 2~3년차가 시작된 지 4개월뿐이라 미완료 매매가 대량 유입 -- 라이브 검증에서 **ACEUSDT 표본이 27건으로 부풀어** 44% 적중률로 추천까지 나갔다(독립 측정상 실제는 3건). 창이 안 차면 None을 돌려주도록 수정하고 회귀 테스트 추가.

**PK 재구성 근거**: 같은 종목이 같은 회차에 단기·장기 양쪽에 뽑힐 수 있어 기존 PK로는 한쪽이 IntegrityError로 사라진다. `recommendations` 테이블이 0행이라 재구성 비용 없음.

**Live 검증 (실 DB 백업 후)**: 장기 후보 15종 4시간봉 수집(SOL 13,188봉 / XRP 18,158봉 등), 사이클 2년차 개방 확인, 장기 추천 **0건**. 0건이 정당함을 개별 확인 -- 진입 신호를 낸 ACE(n=3)·GPS(n=2)는 표본 하한 10에서 탈락, 표본이 충분한 SOL(11)·XRP(31)·BNB(22)·ZEC(18)·TRX(29)는 현재 진입 조건 불충족. **표본 하한이 "안전하게"의 실질 장치로 작동함을 실증.** 4시간봉 수집은 최초 56초 -> 재실행 2초(earliest-probe 수정 효과). 220/220 통과.
**Context**: Code Generation 완료.

---
