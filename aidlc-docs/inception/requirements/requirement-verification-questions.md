# Requirements Clarification Questions — Docker Compose 인프라 + 업비트 API 키 처리

코드를 확인한 결과를 먼저 공유합니다: 현재 `src/upbit_client.py`는 `pyupbit`의 **공개(인증 불필요) 엔드포인트**만 사용합니다 (`get_ohlcv`, `get_tickers`, 공개 ticker REST). `access_key`/`secret_key` 기반 인증 Open API(주문 등)는 코드 어디에서도 사용하지 않습니다. 이 점을 감안해 아래 질문에 답해주세요.

## Question 1
docker-compose는 어떤 목적으로 사용하실 예정인가요? (재시작 정책, 컨테이너 보안 설정 등에 영향)

A) 로컬 개발/테스트용 (필요할 때 띄우고 내리는 용도)

B) 서버(VM 등)에서 상시 운영 (재시작 정책 `unless-stopped`, non-root 유저 등 프로덕션 관례 적용)

C) 둘 다 — 동일 compose 파일로 로컬/서버 모두 사용

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
SQLite 데이터(`data/coin_recommender.db`)를 컨테이너 재생성 후에도 유지하려면 어떤 방식이 좋을까요?

A) 호스트의 `./data` 디렉토리를 바인드 마운트 (호스트에서 파일에 직접 접근 가능, 현재 `db_path` 설정 그대로 사용)

B) Docker named volume 사용 (호스트 경로 신경 안 써도 되지만 파일 직접 접근은 `docker exec`/`docker cp` 필요)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
업비트 인증 API 키(`access_key`/`secret_key`) 관련 처리를 어떻게 할까요?

A) 현재 코드가 인증 API를 쓰지 않으므로 추가 작업 없이 그대로 둔다 (질문하신 "가능한 형태인지"는 "아니오, 현재는 공개 API만 사용"으로 확정)

B) 향후 인증이 필요한 업비트 API(주문 등)를 대비해, `UPBIT_ACCESS_KEY` / `UPBIT_SECRET_KEY`를 지금 설정 체계(`src/config.py`)와 docker-compose 환경변수 주입 경로에 미리 추가한다 (단, 현재 코드 어디서도 참조/사용되지 않는 미사용 설정으로 남음)

C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
"API 키를 실행 단계에서 vm option으로 입력받는다"는 표현을 어떤 방식으로 구현하면 될까요? (Docker는 Java의 `-D` VM 옵션 같은 개념이 없어 보통 컨테이너 런타임 환경변수로 대응합니다)

A) `docker-compose up` 실행 시점의 컨테이너 환경변수로 주입 — 셸 환경변수 또는 커밋되지 않는 `.env` 파일(docker-compose가 같은 디렉토리에서 자동 로드)을 통해 전달, 이미지에는 값이 들어가지 않음

B) 다른 방식을 원함 (예: IntelliJ 실행 설정, 별도 시크릿 관리 도구 등 — 설명 필요)

C) Other (please describe after [Answer]: tag below)

[Answer]: B (intellij 실행 설정)
