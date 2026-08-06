# Logical Components — Unit 2: analytics-backtest

## Ichimoku Reference (테스트 전용)
- **위치**: `tests/ichimoku_reference.py`
- **목적**: `pandas-ta` 출력을 검증하기 위한 독립 참조 구현 (프로덕션 코드에서 사용 안 함)

## As-Of Matcher
- **위치**: `features.py` 내부 함수 (예: `_as_of(points_4h, timestamp)`)
- **목적**: 1시간봉 시각에 대응하는 가장 최근 마감된 4시간봉 지표를 찾음 (BR6)

## 인프라 컴포넌트
- 큐, 캐시 등: 사용하지 않음 (단일 패스 인메모리 계산으로 충분)
