# Unit Test Execution

## Run Unit Tests

### 1. 전체 테스트 실행
```bash
venv\Scripts\pytest -v
```

### 2. 결과 확인
- **기대 결과**: 76개 테스트 전체 통과, 실패 0
- **테스트 커버리지**: 별도 커버리지 도구(coverage.py) 미도입 — 개인 프로젝트 규모라 요구사항에 없었음. 필요 시 `pip install coverage && coverage run -m pytest && coverage report`로 추가 가능
- **테스트 리포트 위치**: 콘솔 출력 (별도 리포트 파일 생성 안 함)

### 3. 유닛별 테스트만 실행 (선택)
```bash
venv\Scripts\pytest tests/test_data_store.py tests/test_upbit_client.py tests/test_binance_client.py tests/test_market_selector.py -v  # Unit 1
venv\Scripts\pytest tests/test_features.py tests/test_backtest.py tests/test_scorer.py -v  # Unit 2
venv\Scripts\pytest tests/test_notifier.py tests/test_pipeline.py tests/test_api.py -v  # Unit 3
```

### 4. Property-Based 테스트만 실행 (Hypothesis)
```bash
venv\Scripts\pytest -k "pbt" -v
```

### 5. 테스트 실패 시
1. 콘솔 출력에서 실패한 테스트와 assertion 메시지 확인
2. Hypothesis 실패 시 출력되는 축소된(shrunk) 반례 확인 — 재현 시드가 함께 출력됨
3. 코드 수정 후 재실행

## 실제 실행 결과 (Code Generation 단계에서 이미 검증됨)

각 유닛 Code Generation 중 실제로 실행해 확인했습니다:
- Unit 1: 21개 통과
- Unit 2: 29개 통과 (오라클 테스트로 `pandas-ta` 정확성 검증 포함)
- Unit 3: 26개 통과
- **합계 76개 전체 통과**, 회귀 없음
