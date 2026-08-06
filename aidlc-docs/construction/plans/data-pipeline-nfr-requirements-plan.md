# NFR Requirements Plan — Unit 1: data-pipeline

## Plan
- [x] Generate `nfr-requirements.md`
- [x] Generate `tech-stack-decisions.md`

## Question Category Evaluation

| 카테고리 | 결정 | 근거 |
|---|---|---|
| Scalability | N/A — 소규모 고정 (20 마켓 x 2 타임프레임 + BTC/ETH) | 개인 로컬 사용, 성장 계획 없음 (요구사항 분석에서 확정) |
| Performance | 매시 1회 실행 창(약 55분 여유) 내 전체 수집을 수 분 내 완료 목표 | 스케줄 주기(FR12)에서 도출되는 자연스러운 제약, 별도 질문 불필요 |
| Availability | N/A | 로컬 단일 인스턴스 (요구사항 분석에서 확정) |
| Security | API 키 불필요 — 업비트/바이낸스 캔들·티커 조회는 공개 엔드포인트 (인증 불필요) | pyupbit 공개 조회 함수와 바이낸스 `/api/v3/klines`는 인증 없이 호출 가능. `.env` 시크릿은 Unit 3(웹훅)에서만 필요 |
| Tech Stack | pyupbit, requests, sqlite3(표준 라이브러리) — 사용자가 이미 지정 | 재확인 불필요 |
| Reliability | HTTP 타임아웃 10초, 실패 시 최대 3회 재시도(1s/2s/4s 지수 백오프), 4xx는 재시도 안 함 | RESILIENCY-10 요구사항 충족을 위한 표준 기본값 — 개인 프로젝트 규모에서 재논의 실익 낮음 |
| Maintainability | 표준 `logging` 모듈, Hypothesis(PBT, 이미 결정) | 이미 결정된 사항 재확인만 |
| Usability | N/A — UI 없음, 내부 라이브러리 계층 | 해당 없음 |

질문 없이 바로 산출물을 생성합니다.
