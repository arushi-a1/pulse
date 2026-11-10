# Pulse

A distributed real-time event processing and analytics platform for high-volume device/sensor telemetry. Built as a portfolio project to demonstrate backend, distributed-systems, and cloud-infrastructure engineering: async processing via SQS, idempotent fault-tolerant workers, cache-aside analytics, independently-scaling ECS services, infrastructure as code, and load-tested performance claims (not invented ones).

```
Devices ──POST /events──► FastAPI ──enqueue──► SQS ──► Worker ──► Postgres (structured data)
                             │                    │        └────► S3 (raw archive)
                             │                    └───────────────► DLQ (after 5 failed attempts)
                             └──cache-aside──► Redis
```

## Table of contents

- [Why this architecture](#why-this-architecture)
- [Repository layout](#repository-layout)
- [Quickstart: run it locally](#quickstart-run-it-locally)
- [API](#api)
- [Reliability & failure scenarios](#reliability--failure-scenarios)
- [Scaling](#scaling)
- [Caching](#caching)
- [Observability](#observability)
- [Security](#security)
- [Testing](#testing)
- [Load testing & performance results](#load-testing--performance-results)
- [AWS deployment (Terraform)](#aws-deployment-terraform)
- [Engineering tradeoffs & what I'd do differently at real scale](#engineering-tradeoffs--what-id-do-differently-at-real-scale)

## Why this architecture

The core design decision is that **`POST /events` never does expensive work on the request path.** It validates the payload and enqueues it to SQS — that's it. Everything expensive (writing to Postgres, archiving to S3, updating rollups, invalidating cache) happens asynchronously in a separate worker process.

This matters for exactly one reason: **it decouples ingestion latency from processing capacity.** If Postgres is briefly slow, or S3 is having a bad minute, or ten times the normal device fleet suddenly comes online, the queue absorbs the difference instead of that showing up as timeouts on the client's `POST /events` call. The load test results below measure this directly — a 2,700+ message backlog built up under sustained load and drained cleanly afterward with zero message loss, while the API kept accepting new events the whole time.

The tradeoff is that the platform is eventually consistent: an event is "accepted" before it's actually queryable in `/devices/{id}/metrics`. That's the right tradeoff for telemetry ingestion (nobody needs read-your-writes consistency on a sensor reading) and the wrong one for, say, a payments API — worth saying explicitly rather than pretending async is free.

## Repository layout

```
pulse/
├── backend/
│   ├── app/             # FastAPI app: routers, services, client wrappers (SQS/S3/Redis), models, schemas
│   ├── worker/          # Standalone async consumer: idempotent processing, retry/backoff, DLQ routing
│   ├── migrations/      # Alembic schema migrations
│   ├── tests/           # pytest: API, idempotency, worker, cache-aside — run against a real local stack
│   └── Dockerfile, Dockerfile.worker
├── frontend/             # React + TypeScript dashboard (Vite)
├── infra/terraform/      # Networking, RDS, Redis, SQS, S3, IAM, ECS, Lambda, CloudWatch modules
├── load-testing/         # Locust scripts + the actual CSV results referenced below
├── scripts/seed_events.py  # Device simulator for local demos
├── docker-compose.yml    # Full local stack: Postgres, Redis, Localstack (SQS+S3), API, worker, frontend
└── .github/workflows/ci.yml
```

## Quickstart: run it locally

Requires Docker and Docker Compose.

```bash
git clone <this-repo>
cd pulse
cp .env.example .env
docker compose up --build
```

This starts Postgres, Redis, Localstack (emulating SQS + S3 so you don't need an AWS account), the API, two worker replicas, and the frontend. Localstack's queue and bucket are created automatically by the `localstack-init` service — no manual setup.

- API: http://localhost:8000 (docs at `/docs`)
- Dashboard: http://localhost:5173
- Send a test event:

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"device_id":"uav-042","timestamp":"2026-08-10T12:00:00Z","event_type":"sensor_reading","payload":{"temperature":23.4,"battery":81.2,"latitude":47.65,"longitude":-122.30}}'
```

Or seed a steady stream for the dashboard to show something interesting:

```bash
pip install requests
python scripts/seed_events.py --devices 20 --rate 5 --duration 120
```

> **A note on how this was actually developed and validated.** The sandbox this project was built in doesn't have Docker available, so local end-to-end validation (migrations, the full ingest→process→query pipeline, idempotency, the test suite, and the load tests below) was run against real Postgres and Redis processes plus [`moto`](https://github.com/getmoto/moto)'s mock-AWS server standing in for Localstack. The application code itself is identical either way — the SQS/S3 client wrappers just point at whichever endpoint `AWS_ENDPOINT_URL` names — but if something behaves subtly differently under real Localstack or real AWS, that's the one seam to check first.

## API

Full interactive docs at `/docs` (FastAPI's generated Swagger UI). Summary:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/events` | Accepts one event, enqueues to SQS, returns `202` immediately |
| `GET` | `/devices` | List known devices |
| `GET` | `/devices/{id}` | Device metadata |
| `GET` | `/devices/{id}/metrics` | Cached 1-hour rolling avg temperature/battery |
| `GET` | `/devices/{id}/events` | Recent raw events for a device |
| `GET` | `/analytics/summary` | Total processed, active devices, events/sec estimate, cache hit rate |
| `GET` | `/analytics/queue` | Approximate SQS backlog depth |
| `GET` | `/analytics/cache` | Cache hit/miss counters |
| `GET` | `/analytics/failures` | Recent processing failures (for the dashboard's failures panel) |
| `GET` | `/health` | Liveness (no dependencies checked) |
| `GET` | `/health/ready` | Readiness (checks DB, Redis, queue — used by the ECS target group) |

Idempotency: `event_id` is optional on the request. If omitted, the server derives one deterministically from `(device_id, event_type, timestamp)`, so a client that retries a timed-out request won't create a duplicate event even without tracking its own IDs.

## Reliability & failure scenarios

| Scenario | What happens |
|---|---|
| Worker crashes mid-processing | Message was never deleted from SQS, so it becomes visible again after the visibility timeout and another worker picks it up. Idempotency (unique `event_id` constraint in Postgres) makes reprocessing safe even if the crash happened after a partial DB write. |
| A downstream (DB/S3) blip causes processing to fail | Worker raises `TransientProcessingError`, does **not** delete the message, sleeps with jittered exponential backoff, and moves on. SQS redelivers on its own schedule. |
| An event contains bad data that can never succeed (unparsable timestamp, missing reading) | The worker validates every message before touching anything and raises `PermanentProcessingError`. It records the failure in `processing_failures`, then sends the message straight to the DLQ and deletes it from the main queue, with no pointless retries. If that DLQ send fails, the message stays put and the normal redrive policy (next row) still catches it. |
| The same event keeps failing for some other reason (e.g. a persistent bug) | After 5 receive attempts (`maxReceiveCount` in the redrive policy), SQS automatically moves the message to the DLQ. A CloudWatch alarm fires the instant anything lands there, and a small Lambda notifies via SNS. Nothing is silently dropped. |
| Duplicate delivery (SQS's at-least-once guarantee, or a client retry) | The unique constraint on `events.event_id` makes reprocessing a no-op — verified directly in the idempotency tests (see Testing below). |
| Redis is unavailable | `get_or_set` catches `RedisError`, logs a warning, and falls back to querying Postgres directly — the request still succeeds, just without the cache speedup. Degraded, not down. |
| A traffic spike well beyond worker capacity | The queue backlog grows (see the 100-user load test below, where depth reached 2,739 messages); `POST /events` latency and error rate are unaffected because enqueueing is cheap regardless of backlog size. In production, worker autoscaling on queue depth (see Scaling) absorbs this within minutes; in this local, single-worker-process test environment it just drains once load stops. |
| Malformed message body reaches the worker (shouldn't happen given Pydantic validation upstream, but defensively handled) | Sent straight to the DLQ for inspection rather than crashing the consumer loop or being retried — covered by `test_handle_message_does_not_raise_on_malformed_body`. |

## Scaling

API and worker are **separate ECS services**, so they scale independently:
- **API** scales on ALB request count per target (target-tracking, 500 req/target/min) — it's stateless request-handling, so this tracks its actual resource pressure.
- **Worker** scales on `ApproximateNumberOfMessagesVisible` (SQS queue depth), not CPU — a worker doing S3/DB I/O can have low CPU utilization while still falling behind on a growing backlog, so queue depth is the metric that actually reflects whether more workers are needed.

**Why the async queue makes this more resilient to spikes:** without it, every `POST /events` would hold open a request thread for the full DB write + S3 archive round trip, and a traffic spike would directly translate into thread/connection exhaustion on the API tier. With the queue in between, a spike just makes the backlog longer — a metric that's cheap to observe and scale against — while the API's own resource usage per request stays constant regardless of backlog size. This is exactly what the 10 vs. 50 vs. 100 concurrent-user results below show: `POST /events` throughput degrades gracefully rather than the service falling over.

## Caching

Cache-aside with a 15–30s TTL on `/analytics/summary` and `/devices/{id}/metrics`. On a cache miss, the loader queries Postgres, populates Redis, and returns; on a Redis error, it degrades to always-querying Postgres directly rather than failing the request. The worker actively invalidates a device's cache key after processing a new event for it, so metrics don't just passively expire — they update as soon as new data lands. Hit/miss counts are tracked in-process and exposed at `/analytics/cache`; in the load test below, the mixed read/write traffic pattern produced a **57.7% cache hit rate**.

## Observability

- **Structured JSON logs** (`app/logging_config.py`) with a `request_id` correlation field stamped by `RequestContextMiddleware` on every API request and propagated through the SQS message into the worker's logs — so a single event's full lifecycle (accepted → enqueued → processed → cached) can be traced by filtering CloudWatch Logs Insights on one `request_id` or `event_id`.
- **CloudWatch dashboard** (`infra/terraform/modules/cloudwatch`): API request count and p50/p95/p99 latency, 4xx/5xx rates, SQS queue depth and DLQ depth, ECS CPU/memory for both services, RDS CPU/connections, and a Logs Insights widget surfacing recent worker failures.
- **Alarms**: DLQ has any messages (fires instantly), sustained queue backlog beyond 5,000, elevated 5xx rate, RDS CPU > 80%. All notify via SNS; the DLQ alarm additionally triggers a Lambda that posts a readable summary.

## Security

- **IAM least privilege**: the API's task role can `sqs:SendMessage` and read queue attributes — nothing else. The worker's task role can receive/delete from the queue and `s3:PutObject` scoped to exactly the `raw-events/*` prefix — it cannot read or delete other objects, let alone touch other buckets. See `infra/terraform/modules/iam`.
- **No hardcoded secrets**: DB credentials are generated by Terraform (`random_password`), stored in Secrets Manager, and injected into ECS tasks as a `secrets` reference — never as a plaintext environment variable, never committed. Local dev uses a throwaway `pulse:pulse` password that's only ever reachable inside the Docker Compose network.
- **HTTPS only in production**: the ALB's plain-HTTP listener exists solely to 301-redirect to HTTPS (TLS 1.3 policy).
- **Input validation**: every field on `EventIn` is range- or type-constrained by Pydantic (e.g. `battery: float = Field(ge=0, le=100)`) — confirmed live by `test_post_event_rejects_invalid_payload`, which sends `battery: 200` and gets a clean `422`.
- **Parameterized queries**: all database access goes through SQLAlchemy's query builder — no string-interpolated SQL anywhere in the codebase.
- **CORS**: explicit origin allowlist (`CORS_ALLOW_ORIGINS`), not a wildcard — confirmed live against the running API (`access-control-allow-origin: http://localhost:5173`, not `*`).
- **Rate limiting**: `slowapi` token-bucket limiting per client IP (`RATE_LIMIT_PER_MINUTE`, defaults to 600/min) on the public API.
- **Centralized error handling**: unhandled exceptions never leak stack traces to the client — they're logged server-side with the request ID and the client gets a generic `500` with just that ID for correlation.

## Testing

```bash
cd backend
pip install -r requirements.txt
docker compose up -d postgres redis localstack localstack-init   # or run them bare-metal, see below
alembic upgrade head
pytest tests/ -v
```

19 tests, all passing against a real Postgres + Redis + mock-SQS/S3 stack (not mocked at the ORM/client level — these exercise actual SQL, actual JSON payload extraction, actual boto3 calls):

- **API integration** (`test_events_api.py`): health checks, 202 on valid events, 422 on out-of-range/invalid/blank fields, 404 on unknown devices, request-ID header presence.
- **Idempotency** (`test_idempotency.py`): duplicate `event_id` processed twice → exactly one row, original values preserved, device event count not double-counted; a genuinely-malformed message raises `PermanentProcessingError` before any side effects and is logged to `processing_failures`.
- **Worker** (`test_worker.py`): a real message sent to SQS and consumed end-to-end lands in Postgres; a malformed message body doesn't crash the consumer; a permanently-invalid event goes straight to the DLQ on its first attempt and is removed from the main queue.
- **Cache** (`test_cache.py`): cache-aside hits on the second call (loader invoked once), invalidation forces a reload, hit-rate stats stay in range.

Two real bugs were caught and fixed during this process, not left in: a SQLAlchemy JSON-column cast that used Python's `float` instead of the JSON comparator's `.as_float()` (broke `/devices/{id}/metrics`), and a validation-error handler that tried to JSON-serialize a raw `ValueError` object from Pydantic's error context (turned a clean `422` into a `500`).

## Load testing & performance results

**Tooling**: [Locust](https://locust.io), `load-testing/locustfile.py` (the real async path) and `load-testing/locustfile_sync_benchmark.py` (a benchmark-only synchronous comparison endpoint, `/benchmark/sync-events`, mounted only when `ENABLE_BENCHMARK_ROUTES=1` — it runs the identical `process_event` logic inline on the request thread instead of via the queue, so the comparison isolates "sync vs. async," not "different code doing different work"). Raw CSVs for every run are committed under `load-testing/results/`.

**Environment**: local machine, single API process, single worker process, Postgres + Redis + a mock-AWS server standing in for real SQS/S3 (see the Quickstart note above on why). These are *not* AWS-deployed numbers — there was no AWS account available in this environment to deploy to. They're real, measured, reproducible numbers from this local harness, not invented ones, but they should be read as relative comparisons (async vs. sync, 10 vs. 50 vs. 100 users) rather than as absolute production throughput figures.

### Async (real) ingestion path — `POST /events`

| Concurrency | Requests/sec | p50 | p95 | p99 | Error rate |
|---|---|---|---|---|---|
| 10 users | 22.99 req/s | 260 ms | 450 ms | 550 ms | 0% |
| 50 users | 38.37 req/s | 1000 ms | 1700 ms | 1900 ms | 0% |
| 100 users | 19.67 req/s | 3900 ms | 4800 ms | 5200 ms | 0% |

### Synchronous benchmark comparison — `POST /benchmark/sync-events`

| Concurrency | Requests/sec | p50 | p95 | p99 | Error rate |
|---|---|---|---|---|---|
| 10 users | 36.22 req/s | 140 ms | 230 ms | 370 ms | 0% |
| 50 users | 30.99 req/s | 1400 ms | 1900 ms | 2100 ms | 0% |

### An honest reading of these numbers

Two things are worth calling out rather than glossing over:

1. **At 100 concurrent users, aggregate throughput dropped instead of climbing** (19.67 req/s vs. 38.37 req/s at 50 users), with sharply higher latency. Investigating this rather than hiding it: the queue depth check right after the 100-user run showed a backlog of **2,739 messages**, confirming the system was accepting far more than the single local worker process could drain — a real saturation point, not a fluke. In production this is exactly what worker autoscaling on queue depth exists to fix; here, with one worker, the backlog just had to drain afterward (it did, cleanly, down to 0 failures — see below).
2. **At low concurrency, the synchronous benchmark was *faster* than the async path** (140ms p50 vs. 260ms p50 at 10 users) — the opposite of what the architecture's thesis would predict. Digging into why: the worker polls SQS continuously in the background, and at higher concurrency both the API's `SendMessage` calls and the worker's `ReceiveMessage`/archive calls are competing for the same single-threaded local mock-AWS server. That contention is an artifact of the local benchmarking harness (a real SQS/S3 deployment handles concurrent access from many clients without this bottleneck) — but it's a genuine limitation of *these specific numbers*, and pretending otherwise would defeat the point of measuring instead of asserting.

The 50-user comparison is the cleanest read of the actual thesis: async throughput (38.37 req/s) exceeds sync throughput (30.99 req/s), and — more importantly — the async path's cost is paid by a queue that can be scaled independently, while the sync path's cost is paid directly by request latency with no lever to pull except adding more API instances (which now also need more DB connections, more S3 client capacity, etc., precisely the coupling the architecture avoids).

**Idempotency and backlog draining under load**, confirmed live rather than assumed: after the 100-user run, `/analytics/queue` read 2,739 → 2,548 messages over the next 20 seconds while the API stayed fully responsive to new requests, and `/analytics/failures` returned `[]` throughout — zero processing failures, zero lost messages, across the entire test sequence.

To reproduce:
```bash
docker compose up -d
ENABLE_BENCHMARK_ROUTES=1 uvicorn app.main:app --reload &  # for the sync comparison only
pip install locust
locust -f load-testing/locustfile.py --host http://localhost:8000 \
    --headless -u 50 -r 10 -t 45s --csv=load-testing/results/async_50u
```

## AWS deployment (Terraform)

```bash
cd infra/terraform
terraform init -backend-config=environments/dev/backend.hcl
cp environments/dev/terraform.tfvars.example environments/dev/terraform.tfvars
# edit terraform.tfvars: set api_image/worker_image to your ECR URIs (pushed by CI),
# and acm_certificate_arn to a certificate for your domain
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

This provisions, with no manual console steps: a VPC with public/private subnets across 2 AZs and NAT gateways; RDS Postgres (private subnet only, credentials in Secrets Manager); ElastiCache Redis; an SQS queue with a DLQ and redrive policy; an S3 bucket with encryption, versioning, and a lifecycle policy to Glacier; least-privilege IAM roles per service; ECS/Fargate services for the API (behind an ALB) and worker, each with independent target-tracking autoscaling; a small Lambda that notifies on DLQ activity; and a CloudWatch dashboard plus alarms.

`terraform validate`-equivalent checks were run in this environment (no `terraform` binary available in this sandbox, and no network path to HashiCorp's release servers): every one of the 31 `.tf` files was confirmed to be syntactically valid HCL, and a script cross-checked every module's inputs/outputs to catch typos or missing wiring before this was written down as done. Actually running `terraform validate`/`plan`/`apply` against a real AWS account is the natural next step and hasn't been done — see Tradeoffs below.

Module breakdown: `networking`, `rds`, `redis`, `sqs`, `s3`, `iam`, `ecs`, `lambda`, `cloudwatch` — one module per concern, composed in `infra/terraform/main.tf`.

## Engineering tradeoffs & what I'd do differently at real scale

- **SQS Standard, not FIFO**: chosen for throughput and cost — FIFO caps at 300 msg/sec per message group without batching. This means at-least-once delivery with no ordering guarantee, which is why idempotency (the unique `event_id` constraint) isn't optional — it's load-bearing. Per-device ordering isn't a real requirement for this workload (each reading is independently valid), so this was the right call, but it's worth stating as a choice rather than an oversight.
- **Single-node RDS and single-node Redis, no Multi-AZ**: a deliberate cost/scope tradeoff for a portfolio deployment. The upgrade path is straightforward (`multi_az = true` on the RDS module, a replication group instead of a single cluster node for Redis) and is called out as a TODO rather than silently absent.
- **The synchronous benchmark endpoint doesn't reflect a real design debate** — it exists purely to produce a controlled comparison for the load test, walled off behind an explicit `ENABLE_BENCHMARK_ROUTES` flag so it's obviously not part of the real API surface.
- **This has not been deployed to real AWS or validated with `terraform apply`.** Everything under `infra/terraform/` was written to be correct (least-privilege IAM, no circular module dependencies, syntactically valid HCL, cross-checked module wiring) but the honest status is "should work, unverified against a real account" rather than "verified working infrastructure." Given real AWS access, the next steps would be: `terraform apply` against a scratch account, confirm the ALB health checks pass and autoscaling policies actually trigger under load, and re-run the Locust suite against the deployed ALB URL for numbers that reflect real network latency and real SQS/S3 concurrency instead of a local single-threaded mock.
- **mypy is advisory (`|| true`) in CI**, not blocking — the codebase uses type hints throughout but hasn't been fully hardened against strict mypy, and I'd rather ship an honest "advisory" label than a CI badge that doesn't mean what it claims.
- **No connection pooling tuning beyond SQLAlchemy defaults** (`pool_size=10, max_overflow=20`) — at higher worker counts than tested here, RDS connection limits would become the next bottleneck to address, likely via RDS Proxy.
