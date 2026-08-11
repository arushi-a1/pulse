# Load testing

Two Locust files:

- `locustfile.py` — the real ingestion path (`POST /events`), plus a light mix of `GET /analytics/summary` and `GET /devices/{id}/metrics` reads, so the test reflects realistic mixed traffic rather than a pure write benchmark.
- `locustfile_sync_benchmark.py` — hits `POST /benchmark/sync-events`, a benchmark-only endpoint (see `backend/app/routers/benchmark.py`) that runs the exact same event-processing logic synchronously, inline on the request thread. This only exists to produce an apples-to-apples comparison against the async path; it's not part of the real API and is only mounted when the API is started with `ENABLE_BENCHMARK_ROUTES=1`.

## Results in this directory

Each run produces four CSVs (Locust's standard `--csv` output): `*_stats.csv` (the summary table — this is what's quoted in the root README), `*_stats_history.csv` (time series over the run), `*_failures.csv`, `*_exceptions.csv`. All are committed as-is — they're the raw evidence backing the numbers in the main README's "Load testing & performance results" section, not just claims.

Runs present: `async_10u`, `async_50u`, `async_100u`, `sync_10u`, `sync_50u` — see the root README for what each shows and, importantly, an honest discussion of where the local test harness itself (a single-threaded mock AWS server standing in for real SQS/S3) becomes the bottleneck rather than the application code.

## Running your own

```bash
docker compose up -d
locust -f load-testing/locustfile.py --host http://localhost:8000 \
    --headless -u 50 -r 10 -t 45s --csv=load-testing/results/my_run
```

Or with the web UI (drop `--headless`) to watch it live: `locust -f load-testing/locustfile.py --host http://localhost:8000`, then open http://localhost:8089.
