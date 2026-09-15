## Why

`docker-compose.yaml`'s `prometheus` service has no retention setting of its own, so retention is whatever `prom/prometheus:latest` defaults to. Checked live against the running stack (read-only — `/api/v1/status/flags`, no restart): the effective values right now are `storage.tsdb.retention.time: 15d` and `storage.tsdb.retention.size: 0B` (Prometheus' own way of saying "not set"). Nothing in the repository states either number, and nothing would state a future image's default if it changed.

This is not a hypothetical risk. Querying the running TSDB for the earliest `chat_request_duration_seconds_count` sample that is not a seeded zero returns `2026-08-07T12:06:00Z` — as of today, exactly 15 days old, sitting on the default's own cutoff. `docs`/`tasks.md` already separately flags the 2026-08-12 run as being "within days of being deleted" under this same default. Neither block has been dropped yet (both are still queryable), but nothing in the stack is stopping either from being dropped on the next compaction pass, because the only thing currently preventing it is an unstated default that a future image pull could also silently change. This is the same class of problem `ruff.toml` exists to fix: a tool's own default silently deciding project behavior, discovered by working it out by hand rather than by reading a config file.

## What Changes

- Configure Prometheus' retention explicitly, so the number in effect is the one in the repository, not the one an unpinned image happens to ship with today.
- **Correction to the literal ask.** This was scoped as a `docker-compose.yaml` change. Checked directly (`docker run --rm prom/prometheus:latest --help`, and `promtool check config` against a candidate file): `--storage.tsdb.retention.time`/`--storage.tsdb.retention.size` are marked `[DEPRECATED]` in the installed Prometheus (3.13.1) — they still work, but the flag's own help text says to use the `storage.tsdb.retention` fields in the config file instead. This repository's Prometheus config already lives in `observability/prometheus.yml` (scrape jobs, paths) rather than in `docker-compose.yaml`'s `command:` — nothing about scrape behavior is set via compose-level flags today, and retention is the same kind of setting. Given a live, verified choice between "explicit but on a flag the tool itself says is going away" and "explicit via the mechanism the tool now recommends, in the file that already owns this kind of setting," this change proposes the latter: `observability/prometheus.yml`'s new `storage.tsdb.retention` block, not a `docker-compose.yaml` `command:` addition. `docker-compose.yaml` itself needs no edit. Flagged here rather than silently substituted, since it departs from how the change was asked for.
- Set `storage.tsdb.retention.time: 90d` and `storage.tsdb.retention.size: 5GB`. `90d` is the owner's decision, made because this stack's history is kept as a portfolio artefact rather than only for debugging; the size bound's reasoning, including what happens if it's ever actually reached, is in `design.md`'s Decisions — not repeated here.
- Apply is a `docker-compose restart prometheus` once this lands (a full process restart, not a container recreate — no image, command, or compose-file field changes) — see Impact.

## Capabilities

### Modified Capabilities
- `observability`: extends the scaffold's `Local Prometheus and Grafana Services with Persistent Storage` requirement, which currently states data survives a restart but says nothing about how long it lives before that. Adds a scenario making retention explicit and repository-readable.

## Impact

- **Affected code**: `observability/prometheus.yml` (new `storage.tsdb.retention` block). `docker-compose.yaml` is unaffected — the retention setting does not go through `command:`, so this proposal's brief not to edit that file is not merely observed but structurally moot.
- **Applying this restarts, not recreates, the `prometheus` container.** Retention is a storage-engine setting fixed at process start; Prometheus' `/-/reload` (or `SIGHUP`) reloads scrape/rule config but not storage settings, so a config-only edit still needs `docker-compose restart prometheus` to take effect — not `up --build` or anything that would change the container's identity. The named volume `prometheus_data` is untouched by a restart either way. **This proposal does not perform that restart** — no container is stopped, started, or recreated by creating this change.
- **Existing data — time-sensitive.** Checked live: neither the 2026-08-12 nor the 2026-08-19 run's blocks have been deleted as of this proposal (both still queryable). Raising retention before a block is dropped keeps it; nothing brings back a block already dropped. Because the oldest currently-held data is already sitting at the 15-day default's own boundary, every day this proposal sits unapplied is a day closer to Prometheus' own compaction pass silently deleting it under the still-unmodified default — this proposal being merely written down changes nothing until it's actually applied (restart, above). That is a reason to apply promptly once this is reviewed, not a reason to act on it from within this proposal, which is scoped to not touch any running container.
- **Affected tests**: none. This is a config-file value with no code path in `backend/`; nothing in `pytest backend/tests/` reads `observability/prometheus.yml`.
- **CI**: unaffected — `.github/workflows/ci.yml`'s backend/frontend gates key off `backend/**`/`frontend/**`; this touches neither.

## Non-Goals

- Editing `docker-compose.yaml` or `observability/prometheus.yml` as part of this proposal, and restarting, recreating, or otherwise touching any running container — this is a proposal only.
- Retention for Grafana's own data (`grafana_data`) — Grafana persists dashboards/config, not time-series history with an aging-out policy; nothing about it is analogous to Prometheus' block-based retention.
- Alerting on approaching either retention bound.
- Revisiting the scaffold's "survives a restart" guarantee itself — unaffected and not reopened here.
