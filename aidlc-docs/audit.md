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
