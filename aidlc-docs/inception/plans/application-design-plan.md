# Application Design Plan — coin-recommender

## Context Analysis

- 사용자가 이미 명확한 프로젝트 구조(9개 컴포넌트 파일)를 제공했으므로, **컴포넌트 경계(Component Identification)는 그대로 채택**한다 — 재질문하지 않음.
- 상세 비즈니스 로직(일목균형표 계산식, 시그널 상태 매칭, 기대수익률 산출)은 이 단계에서 확정하지 않고, 각 유닛의 Functional Design(Construction 단계)에서 다룬다.
- 이 단계에서는 컴포넌트 책임/인터페이스, 서비스 오케스트레이션, 컴포넌트 간 의존관계만 정의한다.

## Design Plan

- [ ] `components.md` 생성 — 9개 컴포넌트의 이름/목적/책임/인터페이스 정의
- [ ] `component-methods.md` 생성 — 컴포넌트별 메서드 시그니처 (입출력 타입, 상세 비즈니스 규칙은 제외)
- [ ] `services.md` 생성 — 오케스트레이션 서비스 정의 (아래 질문 답변에 따라 결정)
- [ ] `component-dependency.md` 생성 — 의존관계 매트릭스, 데이터 흐름
- [ ] `application-design.md` 생성 — 위 4개 문서를 통합한 단일 문서
- [ ] 설계 완결성/일관성 검증

## Design Decisions (질문 없이 확정 — 근거 명시)

| 결정 | 근거 |
|---|---|
| 컴포넌트 경계는 사용자가 제시한 9개 파일 구조 그대로 채택 | 사용자가 이미 명시적으로 지정함 |
| BTC/ETH 레짐 하드필터는 `binance_client.py` 내부 함수로 구현 (별도 파일 없음) | 로직이 짧고(구름대 위치/색 판정), 바이낸스 데이터 소스와 밀접 — 새 파일 추가는 과도한 분리 |
| 시크릿(텔레그램/디스코드 웹훅 URL)은 `.env` + `pydantic-settings`로 분리 로드, `settings.yaml`은 비민감 설정(임계값/기간 등)만 포함 | SECURITY-12(자격증명 하드코딩 금지) 요구사항 충족, pydantic-settings는 이미 선택된 라이브러리로 표준 패턴 |
| 컴포넌트 간 데이터 전달은 pydantic 모델(예: Candle, SignalState, Recommendation)로 타입화 | FastAPI/pydantic 생태계와 일관, 별도 프레임워크 선택 불필요 |

## Question: 파이프라인 오케스트레이션 위치

`POST /run`(수동 트리거)과 스케줄러의 자동 실행은 동일한 전체 파이프라인(후보군 조회 → 수집 → 저장 → 지표 계산 → 레짐 필터 → 백테스트/스코어링 → 알림)을 실행해야 합니다. 이 오케스트레이션 로직을 어디에 둘지 원래 프로젝트 구조에는 명시되지 않아 확인이 필요합니다.

A) `api.py`에 오케스트레이션 함수(예: `run_recommendation_pipeline()`)를 두고, `scheduler.py`가 이 함수를 import해서 호출 — 신규 파일 추가 없이 원래 구조 그대로 유지

B) 신규 파일 `pipeline.py` 하나를 추가해서 오케스트레이션을 전담 — `api.py`와 `scheduler.py` 둘 다 이 모듈을 사용 (원래 9개 파일 구조에 1개 추가)

C) `scorer.py`가 파이프라인의 최종 단계이므로, `scorer.py`에 오케스트레이션 진입점까지 포함

X) Other (please describe after [Answer]: tag below)

[Answer]: B
