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
scheduler polls every 30s for jobs `running` longer than 5 minutes and requeues them back to
`pending` (or `dead` if retries are exhausted).

Requeuing alone isn't enough, though: Redis pub/sub only delivers to clients that are actively
subscribed at publish time, so a job requeued while no worker happens to be listening would sit
`pending` forever with nothing to claim it. To close that gap, every worker runs a catch-up scan
for pending jobs on startup, before it ever blocks on the pubsub loop — so a job is always picked
up either by the next live broadcast or by the next worker that comes online. This was found and
fixed during the live crash test described below.

## Testing

```bash
make test   # pytest tests/ --cov=shared --cov-report=term-missing -v
```

42 unit tests covering the API, worker claim/process/fail/catch-up logic, scheduler requeue
logic, and the database/Redis layers, with 99% coverage on `shared/`. Enforced via GitHub
Actions on every push to `main`.

## Verified

Beyond the unit test suite (mocked, no live infra needed), the full system has been run and
exercised end-to-end against real Postgres/Redis/Docker containers:

- **`docker compose up --build`** — all 6 containers (`postgres`, `redis`, `api`, `worker` x2,
  `scheduler`, `monitor`) started clean, `postgres`/`redis` reporting `healthy`.
- **`GET /health`** — returned `{"api":"ok","redis":"ok","postgres":"ok"}`, HTTP 200.
- **Job lifecycle** — `POST /jobs` → job observed transitioning `pending` → `running` → `done`
  end to end in ~26ms via `GET /jobs/{id}`, `result` populated by the worker.
- **`GET /jobs`, `GET /stats`** — both confirmed returning correct live data from Postgres.
- **Horizontal scaling / no duplicate processing** — scaled to 3 workers (`make scale-workers`),
  fired 20 concurrent `POST /jobs` requests. Result: 21/21 jobs (20 new + 1 prior) reached `done`
  with `attempts == 1` each, zero duplicates. Worker logs show every job broadcast to all 3
  workers, with the losers explicitly logging `already claimed by another worker, skipping` —
  the optimistic-lock race resolving correctly under real concurrent load.
- **Worker crash + scheduler requeue** — submitted a `resize_image` job, killed the claiming
  worker container (`docker kill`, exit code 137) ~80ms into its 200ms simulated processing time
  to leave the job stuck in `running`. The scheduler detected it as stale within its poll
  interval and requeued it:
  ```
  [SCHEDULER] Found 1 stale jobs, requeuing...
  [SCHEDULER] Requeueing job 95945397-... (attempts=1)
  ```
  This surfaced the pub/sub delivery gap described above (job then sat `pending` with no
  subscriber to claim it). After adding the worker's startup catch-up scan and rebuilding the
  image, restarting a worker picked the stranded job up immediately and completed it:
  ```
  [WORKER] Catch-up: found 1 pending job(s) on startup
  [WORKER] Processing job 95945397-... (type=resize_image)
  [WORKER] Job 95945397-... completed: {'output_path': '/processed/crashtest.png', 'size': '800x600'}
  ```
  Final job record: `status: done`, `attempts: 2`, `error` field still shows the original
  timeout message as history of the crash-and-recover cycle.

## Stack

Python 3.12 · FastAPI · Redis 7 (pub/sub) · PostgreSQL 16 (optimistic locking via `version`) ·
Docker Compose · pytest · GitHub Actions
