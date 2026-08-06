# Tech Stack Decisions — Unit 1: data-pipeline

| 기술 | 용도 | 비고 |
|---|---|---|
| pyupbit | 업비트 캔들/티커 조회 | 사용자 지정, 공개 API만 사용 (인증 불필요) |
| requests | 바이낸스 `/api/v3/klines` 호출 | 사용자 지정, timeout=10s 명시 |
| sqlite3 (표준 라이브러리) | 캔들 저장 | 사용자 지정, 별도 ORM 없이 표준 라이브러리로 직접 사용 |
| logging (표준 라이브러리) | 구조화 로그 | 사용자 지정 |
| Hypothesis | PBT-02/03/07/08/09 (Unit1은 주로 PBT-02 라운드트립/멱등성 대상) | Requirements Analysis에서 확정 |

새로 도입하는 라이브러리 없음 — 전량 사용자가 원래 지정한 스택을 그대로 따름.
