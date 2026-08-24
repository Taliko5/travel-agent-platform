## 1. Configuration

- [x] 1.1 Add a `storage.tsdb.retention` block to `observability/prometheus.yml`: `time: 90d`, `size: 5GB`. Not `docker-compose.yaml` — see `proposal.md`/`design.md` D0 for why the originally-scoped file changed.
- [x] 1.2 Validate the edited file with `promtool check config observability/prometheus.yml` (via a throwaway container, e.g. `docker run --rm -v "$(pwd)/observability/prometheus.yml:/test.yml:ro" --entrypoint promtool prom/prometheus:latest check config /test.yml`) before applying it — the exact nested `storage.tsdb.retention.time`/`.size` schema was confirmed this way during proposal, not assumed.
  - `SUCCESS: /test.yml is valid prometheus config file syntax`.

## 2. Apply (time-sensitive — see `design.md` D3)

- [x] 2.1 Confirm neither the 2026-08-12 nor the 2026-08-19 run's data has been dropped yet (e.g. query the earliest non-seeded `chat_request_duration_seconds_count` sample) immediately before applying — if either has already aged out under the old default, say so rather than silently proceeding as if nothing changed.
  - Checked 2026-08-22T11:08:01Z, immediately before restarting: earliest non-seeded `chat_request_duration_seconds_count` sample was still `2026-08-07T12:06:00Z` — 14 days, 23 hours old, inside the still-active `15d` default by less than an hour. Neither run had aged out.
- [x] 2.2 `docker-compose restart prometheus` — a restart, not `up --build` or any operation that recreates the container. Do not run `docker-compose down -v` at any point; it destroys `prometheus_data`, which this change exists to stop losing, not to lose faster.
  - Ran `docker-compose restart prometheus`. Confirmed a restart, not a recreate, from the container's own metadata rather than assumed from the command name: `docker inspect` shows `Created: 2026-08-19T08:53:36Z` (unchanged — same container as before) and `StartedAt: 2026-08-22T11:08:07Z` (the new start). Same container ID throughout.
- [x] 2.3 Re-check `/api/v1/status/flags` (or `/api/v1/status/runtimeinfo`) after the restart and confirm `storage.tsdb.retention.time`/`.size` now read `90d`/`5GB`, not the prior `15d`/`0B`.
  - Post-restart, from the running process: `"storage.tsdb.retention.time": "90d"`, `"storage.tsdb.retention.size": "5GiB"`. `runtimeinfo`'s `storageRetention` reads `"90d or 5GiB"`. Note the unit: `5GB` as written in the config comes back as `5GiB` from the running process — Prometheus' own flag parser, not a typo introduced here. Worth knowing if the number is ever revisited: what's in effect is 5 gibibytes (2^30-byte GB), not 5 decimal gigabytes, a ~7% larger cap than "5GB" would suggest if read literally.
- [x] 2.4 Confirm the pre-restart data — both run dates from 2.1 — is still queryable after the restart, matching the scaffold's own `Restarting the stack preserves prior data` scenario.
  - Re-ran the identical query from 2.1 after the restart: earliest non-seeded `chat_request_duration_seconds_count` sample is still `2026-08-07T12:06:00Z` — the exact same value, not merely "still present in some form." Latest non-seeded sample is `2026-08-22T11:08:00Z`, seconds before the restart's `StartedAt`, showing scraping continued right up to the restart with no gap in what's held. `prometheus_data` survived intact.

## 3. Record

- [x] 3.1 Record the before/after retention values and the confirmation from 2.3–2.4 somewhere durable (this change's own notes) rather than relying on having checked it once.
  - Recorded above, in 2.1–2.4, with the actual queried values rather than a paraphrase. Before: `storage.tsdb.retention.time: 15d`, `.size: 0B`. After: `90d` / `5GiB`.
