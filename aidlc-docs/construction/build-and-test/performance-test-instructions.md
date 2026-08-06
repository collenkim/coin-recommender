# Performance Test Instructions

## 적용 범위

정식 부하/스트레스 테스트 도구(JMeter, k6 등)는 도입하지 않습니다 — 개인 로컬 사용 도구로 동시 사용자나 처리량 요구사항이 없습니다 (요구사항 분석에서 확정). 대신 NFR에서 정의한 soft target을 실제 실행 시간으로 확인합니다.

## Soft Target 확인 (실측 방법)

```bash
# POST /run 실행 시간을 측정 (PowerShell 예시)
Measure-Command { Invoke-WebRequest -Uri "http://127.0.0.1:8123/run" -Method POST }
```

- **목표**: 매시 실행 창(스케줄러가 정각+5분에 실행, 다음 실행까지 약 55분) 내 완료 — 수 분 내 완료를 soft target으로 설정 (Unit 1/2/3 NFR Requirements)
- **실측 결과**: Build and Test 단계에서 실제 업비트/바이낸스 API로 1회 실행한 결과, 정확한 소요 시간은 별도로 측정하지 않았으나 요청이 타임아웃(180초) 없이 정상 완료됨 — soft target 충족

## 향후 후보군이 늘어나는 경우

`top_n_candidates`(`config/settings.yaml`)를 늘리면 수집 시간이 선형적으로 증가합니다. 크게 늘릴 계획이 있다면 이 문서를 갱신해 실제 측정치를 기록하는 것을 권장합니다.
