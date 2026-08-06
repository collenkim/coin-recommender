# Code Generation Summary — Unit 2: analytics-backtest

## Generated Files

### Application Code
- `src/features.py` — `IchimokuPoint`, `compute_ichimoku` (pandas-ta 래핑), `is_bullish`, `as_of`
- `src/backtest.py` — `SignalStats`, `golden_cross_event`, `compute_signal_stats`, `aggregate_stats`
- `src/scorer.py` — `Recommendation`, `check_market_regime`, `generate_recommendations`
- `requirements.txt`에 `pandas==3.0.5`, `pandas-ta==0.4.71b0` 추가

### Tests (`tests/`)
- `ichimoku_reference.py` — 오라클 테스트용 순수 pandas 참조 구현 (프로덕션 미사용)
- `test_features.py` — 오라클 대조, 워밍업 경계, PBT-03(is_bullish 불변식), as_of (10개)
- `test_backtest.py` — golden_cross_event, compute_signal_stats 통합 시나리오, PBT-03(hit_count<=n, 평균값) (11개)
- `test_scorer.py` — 레짐 AND 조합, 하드필터 단락, 시그널 없음 스킵, 임계값/N=0 제외, 정렬 (8개)

## 실행 검증 (실제 실행 완료 — 총 50개 테스트 통과, Unit 1 포함 회귀 없음)

### 실행 중 발견한 중요 사항과 정정 3건

1. **환경 변경 (사용자 승인)**: `pandas-ta`를 PyPI에서 설치해보니 남은 버전(0.4.71b0)이 Python 3.12+ 요구 — 3.11.9 venv와 충돌. 예전 안정 버전은 PyPI에서 사라진 상태. 사용자에게 확인 후 **Python 3.12.10으로 업그레이드**하고 venv 재생성, Unit 1 테스트로 회귀 없음 확인.

2. **핵심 계산 버그 사전 방지 (실측)**: business-rules.md BR1에서 "26기간 시프트"로 가정했으나, `pandas-ta.ichimoku()`의 실제 출력을 고정 시드 데이터로 직접 검증한 결과 **25기간 시프트**임을 확인 (오차 0으로 정확히 일치). 텍스트북 설명과 다르지만 라이브러리의 실제 동작을 그대로 채택 — 이 검증 없이 진행했다면 구름 판정이 한 봉씩 어긋나는 조용한 버그가 됐을 것.

3. **코드 버그**: `compute_ichimoku`가 입력 캔들이 너무 적을 때(`pandas-ta`가 `(None, None)` 반환) `NoneType is not subscriptable`로 크래시 — 짧은 이력에서 모든 지표를 None으로 반환하도록 수정.

4. **테스트 버그**: 초기 워밍업 테스트가 `senkou_a`와 `senkou_b`의 워밍업 길이가 다르다는 걸 놓치고 하나로 뭉뚱그려 잘못된 어설션을 작성 — 실제 실행 결과(각각 인덱스 50, 76부터 값 존재)에 맞춰 분리해 수정.

```
venv\Scripts\pytest -v
# 50 passed
```

## 아직 없는 것 (Unit 3에서 추가)
- `pipeline.py`, `notifier.py`, `scheduler.py`, `api.py`
- `generate_recommendations()`는 아직 어디서도 호출되지 않음 — Unit 3의 Pipeline이 오케스트레이션
