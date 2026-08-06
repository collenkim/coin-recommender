# Build Instructions

## Prerequisites
- **Python**: 3.12 이상 (`pandas-ta`가 PyPI에 유지 중인 버전이 3.12+ 요구 — README.md 참조)
- **OS**: Windows (개발/검증 환경), 다른 OS에서도 동작 가능하나 미검증
- **환경 변수**: `.env` (선택) — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL` 중 필요한 것만 설정, 없으면 알림 없이 동작

## Build Steps

### 1. 가상환경 생성 및 의존성 설치
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. 환경 설정
```bash
copy .env.example .env
# .env 편집: 알림을 쓰려면 TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 또는 DISCORD_WEBHOOK_URL 채우기
```

### 3. 빌드 확인
Python 프로젝트라 별도 컴파일 단계는 없음. 임포트가 성공하면 빌드 성공으로 간주:
```bash
venv\Scripts\python -c "import src.api"
```

### 4. 빌드 성공 확인
- **기대 결과**: 에러 없이 종료
- **산출물**: 없음 (인터프리터 언어, `src/`가 곧 실행 가능한 애플리케이션)

## Troubleshooting

### `pandas-ta` 설치 실패
- **원인**: Python 버전이 3.12 미만
- **해결**: Python 3.12+ 설치 후 venv 재생성 (Unit 2 Code Generation에서 실측 확인된 제약)

### `ModuleNotFoundError: No module named 'src'`
- **원인**: 프로젝트 루트가 아닌 곳에서 실행
- **해결**: 저장소 루트(`coin-recommend/`)에서 실행, 또는 `pytest`/`uvicorn`을 루트에서 실행
