# coin-recommender

1시간봉 거래량 확인 돌파 + 일목균형표 추세 조건으로, 24시간 안에 +3%를 터치할 확률이 높은 **바이낸스** 알트코인을 추천하는 FastAPI 서비스.

BTC가 강한 상승장(30일 +20% 초과) 또는 반등 상승장(30일 하락 중이나 저점 대비 +10% 초과)일 때만 진입합니다 — 그 외 구간은 5년 실측에서 목표 달성률이 무작위 진입과 구분되지 않았습니다. 추천마다 진입가·매도가(+3%)·손절가(-2%)와 과거 실측 도달 확률을 함께 제공합니다.

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
- `.env`: 시크릿 (텔레그램 봇 토큰, 디스코드/슬랙 웹훅 URL 등) — 커밋 금지

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

## Docker로 실행 (서버 상시 운영용)

```bash
cp .env.example .env   # 아직 안 했다면; 텔레그램/디스코드/슬랙 시크릿 채우기
docker-compose up -d --build
```

- SQLite DB는 호스트 `./data`에 바인드 마운트되어 컨테이너를 재생성해도 유지됩니다.
- `.env`는 이미지에 포함되지 않고 `docker-compose up` 실행 시점에 컨테이너 환경변수로 주입됩니다 (커밋 금지).
- 바이낸스 공개(인증 불필요) 캔들/티커 엔드포인트만 사용하므로 거래소 API 키는 필요/사용하지 않습니다.

### 실행 확인 (스모크 테스트)

컨테이너가 실제로 정상 동작하는지 확인하는 방법입니다 (아래 `## 테스트`의 `pytest`와는 별개 — pytest는 Docker 없이 로컬에서 코드 자체를 검증하고, 여기는 8000 포트로 뜬 실제 컨테이너를 확인합니다).

```bash
docker-compose ps                              # STATUS 컬럼에 (healthy) 나오는지 확인
curl http://localhost:8000/health               # {"status":"ok","db_connected":true} 기대
curl http://localhost:8000/recommendations      # 최신 추천 결과 (아직 한 번도 안 돌았으면 recommendations: [])
curl http://localhost:8000/recommendations?limit=3   # 최근 3회차 이력까지 조회
curl -X POST http://localhost:8000/run           # 수동으로 파이프라인 즉시 실행 (실제 바이낸스 호출, 몇 분 걸릴 수 있음)
docker-compose logs -f                           # 실시간 로그로 스케줄러/에러 확인
```

## 테스트

```bash
pytest
```
