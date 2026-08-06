# Logical Components — Unit 1: data-pipeline

## RetryHelper
- **목적**: 재시도+백오프 로직을 UpbitClient/BinanceClient가 공유
- **위치 제안**: `src/upbit_client.py`와 `src/binance_client.py`가 각자 사용하는 작은 내부 유틸 함수 (신규 파일 불필요, 원래 구조 유지)

## DataStore Connection Manager
- **목적**: SQLite 연결의 열기/닫기, WAL 모드 설정을 일관되게 처리
- **위치**: `data_store.py` 내부 — 각 public 메서드가 컨텍스트 매니저로 연결을 열고 작업 후 닫음

## 인프라 컴포넌트
- 큐, 캐시, 별도 서킷브레이커 라이브러리: 사용하지 않음 (이 유닛의 규모/트래픽 패턴에 불필요)
