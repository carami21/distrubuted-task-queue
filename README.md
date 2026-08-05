# Distributed Task Queue System

[![CI](https://github.com/carami21/distrubuted-task-queue/actions/workflows/ci.yml/badge.svg)](https://github.com/carami21/distrubuted-task-queue/actions/workflows/ci.yml)

Distributed async job processing system built as 4 independent microservices, wired together
with Redis pub/sub for job distribution and PostgreSQL for durable job state. Jobs are submitted
via a REST API, claimed by horizontally-scalable workers using optimistic locking (so no two
workers ever process the same job twice), and a scheduler detects and requeues jobs stuck behind
crashed workers.

## Architecture

```
  Client
    │
    ▼
  [API Service :8000]          [Health Monitor :8001]
    │  ┌──────────────────────────────┐
    │  │     PostgreSQL (job state)   │
    │  └──────────────────────────────┘
    │
    ▼
  [Redis pub/sub]
    │         │
    ▼         ▼
[Worker 1] [Worker 2]    ← horizontally scalable
              │
    [Scheduler] ← detects stale jobs, requeues
```

## Job State Machine

```
         POST /jobs
              │
              ▼
          [PENDING]  ──── scheduler detects stale ────┐
              │                                        │
    worker picks up via Redis                          │
              │                                        │
              ▼                                        │
          [RUNNING]  ──── timeout (>5 min) ───────────┘
              │
         ┌────┴────┐
         ▼         ▼
      [DONE]   [FAILED]
                   │
            attempts < 3?
                   │
             ▼         ▼
          requeue    [DEAD]   (dead-letter)
```

## Endpoints

| Method | Path             | Description                              | Status |
|--------|------------------|-------------------------------------------|--------|
| POST   | /jobs            | Create job, publish to Redis              | 201    |
| GET    | /jobs            | List jobs (?status=pending&limit=50)      | 200    |
| GET    | /jobs/{job_id}   | Get single job by ID                      | 200    |
| DELETE | /jobs/{job_id}   | Cancel a pending job (set status=dead)    | 204    |
| GET    | /stats           | Count of jobs per status                  | 200    |
| GET    | /health          | Redis + Postgres liveness (monitor :8001) | 200    |

## Quickstart

```bash
git clone https://github.com/carami21/distrubuted-task-queue.git
cd distrubuted-task-queue
docker compose up --build
```

This starts 6 containers: `postgres`, `redis`, `api`, `worker` (x2), `scheduler`, `monitor`.

## Demo

```bash
make demo
```

Submits a `send_email` job and lists all jobs. Or manually:

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type":"send_email","payload":{"to":"test@example.com"}}'

curl http://localhost:8000/jobs/<job_id>
```

Watch the job transition `pending` → `running` → `done` within a second or two.

## Scaling

```bash
make scale-workers   # docker compose up --scale worker=3 -d
```

Spin up additional worker replicas. Optimistic locking on the `jobs.version` column guarantees
no two workers can both win a claim on the same job, so scaling out never causes duplicate
processing — a worker's `UPDATE ... WHERE job_id = ? AND version = ? AND status = 'pending'` only
succeeds for exactly one concurrent caller; every loser sees `0` rows affected and moves on.

## Fault Tolerance

If a worker crashes mid-job, the job is left in `running` with a stale `started_at`. The
scheduler polls every 30s for jobs `running` longer than 5 minutes and requeues them to
`pending` (or `dead` if retries are exhausted), so no job is lost to a worker crash.

## Testing

```bash
make test   # pytest tests/ --cov=shared --cov-report=term-missing -v
```

40 unit tests covering the API, worker claim/process/fail logic, scheduler requeue logic, and
the database/Redis layers, with 98%+ coverage on `shared/`. Enforced via GitHub Actions on every
push to `main`.

## Stack

Python 3.12 · FastAPI · Redis 7 (pub/sub) · PostgreSQL 16 (optimistic locking via `version`) ·
Docker Compose · pytest · GitHub Actions
