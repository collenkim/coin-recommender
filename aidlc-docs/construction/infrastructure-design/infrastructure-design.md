# Infrastructure Design — Docker Compose

## Scope
One deployable unit: the existing single FastAPI process (`uvicorn src.api:app`), which includes the in-process APScheduler and reads/writes the SQLite file DB. This mirrors the existing NFR Design decision ("no cloud infra, local single instance") — docker-compose packages that same single-instance architecture, it does not change it.

## Category Evaluation
| Category | Decision | Rationale |
|---|---|---|
| Deployment Environment | Single Docker container, run via `docker-compose up` on a VM (per Requirements Q1) | No CI/CD requested; manual image build + up is sufficient |
| Compute Infrastructure | One `api` service, default resource limits (none set) | Single low-traffic personal service; no scaling requirement stated |
| Storage Infrastructure | SQLite file, host bind mount `./data:/app/data` (per Requirements Q2) | Matches existing `db_path=data/coin_recommender.db`; already gitignored |
| Messaging Infrastructure | N/A | No queue/broker in the existing architecture |
| Networking Infrastructure | Single port mapping `8000:8000`, no reverse proxy/LB | Single container, no multi-instance routing need |
| Monitoring Infrastructure | Docker `healthcheck` calling existing `GET /health` | Reuses RESILIENCY-06 endpoint already implemented; no new monitoring stack requested |
| Shared Infrastructure | N/A | Single service, nothing to share |

## Deployment Architecture
```
┌─────────────────────────────┐
│  Host (VM)                  │
│  ┌────────────────────────┐ │
│  │ docker-compose          │ │
│  │  service: api            │ │
│  │  - image: built from     │ │
│  │    ./Dockerfile          │ │
│  │  - port 8000:8000        │ │
│  │  - env_file: .env         │ │
│  │    (TELEGRAM_*, DISCORD_*)│ │
│  │  - volume: ./data:/app/data│
│  │  - healthcheck: GET /health│
│  │  - restart: unless-stopped │
│  └────────────────────────┘ │
└─────────────────────────────┘
```

## Secrets Handling
- `.env` (already gitignored) holds `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL`.
- docker-compose loads it via `env_file: .env` — values reach the container as process environment variables at `docker-compose up` time, never baked into the image (`.dockerignore` excludes `.env` from the build context).
- No Upbit key handling added — confirmed unused in code (Requirements Q3).

## Explicit Non-Coverage
- No Upbit `access_key`/`secret_key` config — out of scope per Requirements.
- No CI/CD, no orchestration platform, no reverse proxy — out of scope per Requirements Q1 and prior NFR Design decision.
