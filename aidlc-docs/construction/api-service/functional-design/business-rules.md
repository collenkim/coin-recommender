# Business Rules — Unit 3: api-service

## BR1. 파이프라인 오케스트레이션 순서 (services.md 재확인)

1. `MarketSelector.get_candidate_markets()`
2. 후보/BTC/ETH 캔들 수집 및 저장 (Unit 1)
3. `Scorer.generate_recommendations()` (Unit 2) — 내부에서 레짐 하드필터 적용
4. 결과를 `pipeline_runs` + `recommendations` 테이블에 저장
5. `Notifier.send_notification()` 호출 (best-effort, 실패해도 파이프라인은 성공으로 간주)

## BR2. 동시 실행 방지

프로세스 내 락(예: `threading.Lock`)으로 파이프라인 중복 실행을 막는다. 이미 실행 중일 때 `POST /run`이 호출되면 파이프라인을 새로 시작하지 않고 "이미 실행 중" 응답(409)을 반환한다. 스케줄러 잡도 동일 락을 공유한다.

## BR3. 결과 저장은 항상 발생, 알림은 best-effort

파이프라인이 레짐 하드필터로 추천 0개를 반환하더라도 `pipeline_runs`에 실행 기록은 남긴다 (regime_bullish=False로). `Notifier` 전송이 실패(네트워크 오류 등)해도 예외를 상위로 전파하지 않고 로그만 남기며, 이미 저장된 결과는 그대로 유지된다.

## BR4. 알림 채널

`.env`에 `TELEGRAM_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL` 중 설정된 것마다 각각 발송. 하나만 설정되면 하나만, 둘 다 없으면 알림을 보내지 않고 로그만 남긴다 (에러 아님).

## BR5. 알림 메시지 형식

```
[coin-recommender] {run_time} 추천 결과

- {market}: 기대수익률 {expected_return:.1%} (과거 {n}회 중 {hit_count}회 적중)
- ...

(추천 없음이면: "이번 회차 추천 없음")
```

## BR6. GET /recommendations 응답

`pipeline_runs`에서 가장 최근 `run_time`을 조회 → 해당 `run_time`의 `recommendations` 행 전체 반환. 아직 한 번도 실행되지 않았으면 (`pipeline_runs`가 비어있으면) 빈 결과 + `run_time: null`을 반환 (에러 아님, 정상적인 초기 상태).

## BR7. GET /health

DB 연결을 확인하는 간단한 쿼리(`SELECT 1`)를 실행해 성공하면 `{"status": "ok", "db_connected": true}`, 실패하면 500과 함께 `{"status": "error", "db_connected": false}` 반환 (RESILIENCY-06).

## BR8. POST /run 동기/비동기

`POST /run`은 파이프라인 실행이 끝날 때까지 기다렸다가(동기) 결과를 반환한다 (스펙에 "수동 트리거"라고만 되어 있고 별도 비동기 요구가 없으므로 가장 단순한 방식 채택 — 매시 실행이 몇 분 내 끝나는 규모라 응답 지연이 크지 않음).
