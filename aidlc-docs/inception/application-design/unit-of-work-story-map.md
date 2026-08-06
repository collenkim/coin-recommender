# Unit of Work — Requirements Map — coin-recommender

**참고**: User Stories 단계가 스킵되어(개인 단일 사용자 프로젝트), 스토리 대신 `requirements.md`의 기능 요구사항(FR)을 유닛에 매핑합니다.

## Unit 1: data-pipeline
- FR1. 후보군 선정
- FR2. 데이터 수집 (업비트/바이낸스)
- FR3. 부트스트랩 및 증분 수집
- FR4. 저장 (SQLite upsert)

## Unit 2: analytics-backtest
- FR5. 일목균형표 계산
- FR6. 추세 필터 (4시간봉)
- FR7. 진입 시그널 (1시간봉)
- FR8. 시장 레짐 필터 (하드 필터)
- FR9. 시그널 상태 정의 및 기대수익률 계산
- FR10. 추천 필터링

## Unit 3: api-service
- FR11. API (`GET /recommendations`, `POST /run`)
- FR12. 스케줄링
- FR13. 알림
- FR14. 인증 (해당 없음 정책을 API 계층에 반영)

## Coverage Check

FR1~FR14 전체가 유닛에 매핑되었습니다. 매핑되지 않은 요구사항 없음.
