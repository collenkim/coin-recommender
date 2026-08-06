# Logical Components — Unit 3: api-service

## Pipeline Lock
- **위치**: `pipeline.py` 모듈 전역 `threading.Lock()`
- **목적**: 스케줄러 잡과 `POST /run`의 동시 실행 방지

## Global Exception Handler
- **위치**: `api.py`
- **목적**: 처리되지 않은 예외에 대한 일관된 500 응답

## 인프라 컴포넌트
- 큐/캐시: 사용하지 않음
