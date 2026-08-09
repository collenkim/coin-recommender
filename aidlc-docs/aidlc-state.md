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

## Current Status
- **Lifecycle Phase**: COMPLETE (base project) + 3 follow-up features delivered and approved (Docker Compose infra; 추천 결과 적중 판별; 바이낸스/업비트 거래소별 추천 5개씩 포함)
- **Current Stage**: Binance/Upbit balanced-recommendation feature complete (2026-08-10). Operations remains a placeholder with no defined steps (per core-workflow.md)
- **Next Stage**: None — all delivered work approved. Future work would re-enter as a new AI-DLC request (e.g. "Using AI-DLC, add X")
- **Status**: Done
