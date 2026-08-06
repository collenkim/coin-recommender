# NFR Requirements — Unit 1: data-pipeline

## Performance
- 매시 1회 실행 창(스케줄 주기 1시간, 실행은 정각+5분) 내에서 전체 후보 20개 + BTC/ETH 수집이 수 분 내 완료되는 것을 목표로 함 (하드 SLA 아님, 개인 도구 수준의 soft target)

## Scalability
- N/A — 후보군 20개 고정, 성장 계획 없음 (요구사항 분석에서 확정)

## Availability
- N/A — 로컬 단일 인스턴스, 클라우드 미배포 (요구사항 분석에서 확정)

## Reliability (RESILIENCY-10)
- 모든 외부 HTTP 호출(업비트, 바이낸스)에 명시적 타임아웃: 10초
- 일시적 실패(타임아웃, 연결 오류, 5xx) 시 최대 3회 재시도, 지수 백오프(1s → 2s → 4s)
- 4xx 응답(잘못된 마켓 코드 등)은 재시도하지 않고 즉시 실패 처리 후 해당 마켓 스킵
- 개별 마켓 수집 실패가 전체 파이프라인 실행을 막지 않음 (business-rules.md BR7)

## Security
- SECURITY-12: 이 유닛은 API 키/자격증명이 전혀 필요 없음 — 업비트/바이낸스 캔들·티커 조회 엔드포인트는 공개(인증 불필요)이므로 시크릿 관리 대상 없음
- SECURITY-15: 모든 외부 호출과 DB 연산에 명시적 예외 처리, 실패 시 안전하게 해당 항목만 제외(fail closed at the item level, not process level)
- 그 외 SECURITY 규칙(01/02/04/06/07/08/09/10/11/13/14): N/A — 이 유닛에는 저장소 암호화 대상(로컬 SQLite, 요구사항에서 N/A 확정), 네트워크 인프라, 인증 엔드포인트가 없음

## Maintainability
- `logging` 표준 모듈로 구조화 로그 (수집 성공/스킵/실패를 마켓 단위로 기록)
- PBT(Hypothesis)로 `DataStore.upsert_candles`/`get_candles` 라운드트립 및 멱등성 테스트 (PBT-02, 이미 확정)

## Usability
- N/A — UI 없는 내부 라이브러리 계층
