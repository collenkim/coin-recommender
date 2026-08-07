# Code Generation Plan — Unit 3: api-service (추천 결과 사후 판별)

Story: 추천 결과 적중 판별 및 학습 반영 (BR9, BR10)

- [x] Step 1: `src/data_store.py` — `recommendations` 테이블 마이그레이션(신규 nullable 컬럼 3개) + `RecommendationRecord` 확장
- [x] Step 2: `src/data_store.py` — `get_pending_evaluations`, `record_outcome`, `get_recent_runs` 추가; `get_latest_run` 새 필드 반영
- [x] Step 3: `src/pipeline.py` — `evaluate_pending_outcomes` 추가, `run_recommendation_pipeline`에서 락 안에서 호출 (BR9)
- [x] Step 4: `src/api.py` — `RecommendationOut`/`RunSummary`/`RecommendationsResponse` 확장, `GET /recommendations?limit=` 구현 (BR10)
- [x] Step 5: 단위 테스트 — data_store(마이그레이션 안전성, pending/record/recent_runs), pipeline(평가 배치 호출 및 격리), api(limit 파라미터 동작)
