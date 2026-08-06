# coin-recommender

1시간봉/4시간봉 일목균형표(구름대) 기반으로 하루 안에 +4% 상승 가능성이 높은 업비트 알트코인을 추천하는 FastAPI 서비스.

전체 요구사항/설계 문서는 `aidlc-docs/`를 참고하세요 (AI-DLC 워크플로우로 생성됨).

## 요구 사항

**Python 3.12 이상** — `pandas-ta`가 PyPI에 유지 중인 버전(0.4.71b0)이 Python 3.12+를 요구해서, 원래 목표였던 3.11+에서 상향 조정되었습니다 (Unit 2 Code Generation 중 확인).

## 설치

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env   # 필요 시 웹훅 URL 등 채우기
```

## 설정

- `config/settings.yaml`: 비민감 설정 (임계값, 기간 등)
- `.env`: 시크릿 (텔레그램/디스코드 웹훅 URL 등) — 커밋 금지

## 진행 상태

- [x] Unit 1: data-pipeline (후보군 선정, 캔들 수집/저장)
- [x] Unit 2: analytics-backtest (일목균형표, 백테스트, 스코어링)
- [x] Unit 3: api-service (FastAPI, 스케줄러, 알림)

## 실행

```bash
uvicorn src.api:app --reload
```

- `GET /recommendations` — 최신 추천 결과 조회
- `POST /run` — 수동 실행
- `GET /health` — 헬스체크

## 테스트

```bash
pytest
```
