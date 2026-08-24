## Context

`docker-compose.yaml`'s `prometheus` service sets no retention flag and no `storage:` block in `observability/prometheus.yml`, so Prometheus runs on whatever `prom/prometheus:latest` defaults to. Checked live against the running container (read-only HTTP calls, no restart):

```
$ curl -s http://localhost:9090/api/v1/status/flags | grep retention
"storage.tsdb.retention.size": "0B"
"storage.tsdb.retention.time": "15d"
$ curl -s http://localhost:9090/api/v1/status/runtimeinfo | grep storageRetention
"storageRetention": "15d"
```

`0B` is Prometheus' way of saying the size bound is unset — time-only retention, unbounded on disk. Current image is `prom/prometheus:latest`, resolved version `3.13.1`.

The mechanism assumed when this change was scoped — a `docker-compose.yaml` `command:` entry passing `--storage.tsdb.retention.time`/`--storage.tsdb.retention.size` — turns out not to be the one Prometheus itself currently recommends:

```
$ docker run --rm prom/prometheus:latest --help | grep -A5 storage.tsdb.retention.time
--storage.tsdb.retention.time=STORAGE.TSDB.RETENTION.TIME
                    [DEPRECATED] How long to retain samples in storage.
                    ... This flag has been deprecated, use the
                    storage.tsdb.retention.time field in the config
                    file instead.
```

The config-file field exists and validates (checked with `promtool check config` against a candidate file, not assumed from documentation memory):

```yaml
storage:
  tsdb:
    retention:
      time: 90d
      size: 5GB
```

`observability/prometheus.yml` is where this repository already keeps every other piece of Prometheus configuration (scrape jobs, `metrics_path`); `docker-compose.yaml` carries none of it. See D0.

Real data currently in the TSDB (checked live, not assumed, re-confirmed at time of this revision): the earliest non-seeded `chat_request_duration_seconds_count` sample is still `2026-08-07T12:06:00Z` and still queryable — as of this revision, 15 days old, on the default's own boundary. `docker exec ... du -sh /prometheus` reports `4.4M` for the whole data directory, covering that span plus the 2026-08-12 and 2026-08-19 load runs and roughly ten days of otherwise-idle scraping (143 active series, per `/api/v1/status/tsdb`).

## Goals / Non-Goals

**Goals:**
- State Prometheus' retention explicitly, in the repository, rather than leaving it to an image default nobody wrote down.
- Choose values with stated reasoning tied to this stack's actual purpose and actual measured growth, not round numbers picked for their own sake.
- Decide, rather than default into, whether disk usage is bounded as well as time.
- Say plainly what this change can and cannot do for data already in `prometheus_data`, given the specific run dates this repository already refers to elsewhere.

**Non-Goals:**
- Implementing the change — this document, `proposal.md`, `tasks.md`, and the spec delta are the entire deliverable. No config file is edited, no container is touched.
- Alerting or dashboarding on retention/disk usage.
- Grafana's own persisted data — a different kind of state with no aging-out policy to make explicit.

## Decisions

### D0 — Retention goes in `observability/prometheus.yml`, not `docker-compose.yaml`
Not the file this change was originally scoped to touch — see `proposal.md`'s "Correction to the literal ask." Restated here because it's the decision everything else in this document assumes: the CLI flags that would have gone in a `docker-compose.yaml` `command:` are `[DEPRECATED]` in the installed Prometheus version (checked via `--help`, not assumed), in favor of a `storage.tsdb.retention` block in the config file, which validates via `promtool check config` against a candidate file. Using a flag the tool itself says is going away is the exact failure mode this change exists to avoid one layer up — the point is to stop depending on something that can change out from under this repository without anyone noticing, and a deprecated flag is a second version of that same risk, not a fix for the first one.

### D1 — `storage.tsdb.retention.time: 90d`
Owner's decision, not derived here: retention is 90 days because this stack's observability history is kept as a portfolio artefact rather than only for debugging — a reader should be able to open the dashboard months after a run and still see it. That is the reasoning of record for this number; it is not re-derived or second-guessed in this document. `90d` is also six times the `15d` default it replaces, which is the concrete way that purpose shows up in the config rather than staying only a stated intent.

### D2 — Bound disk too: `storage.tsdb.retention.size: 5GB`, deliberately set, deliberately dormant
Time-only retention on a stack left running grows without a ceiling, and `90d` is six times the default it replaces — six times the accumulation, with nothing else limiting it. Both dimensions of growth are plausible here: `llm_call_duration_seconds` and `rag_retrieval_total` are declared but not yet recording (`step8-metric-design` design.md), and picking up real call sites for either adds series. `--storage.tsdb.retention.size` exists for exactly this. **Decision: set it.** Not setting it would be an omission wearing the shape of a decision — nothing in "leave it unset" states a reason, it just inherits whatever disk growth happens to occur.

**What happens if it's ever actually reached, stated plainly because it matters here specifically:** Prometheus enforces `retention.size` the same way it enforces `retention.time` — by deleting whole blocks, oldest first, until usage is back under the cap. If the size limit binds before the time limit ever would, the data it deletes is the *oldest* data still held — which, for this stack, is precisely the portfolio artefact `90d` exists to keep. A size cap that actually fires under normal operation would silently claw back the retention window D1 just set, from the wrong end: newest data survives, oldest (most portfolio-relevant) data is what goes.

That consequence is why the value is chosen to stay dormant, not tuned to bite. Measured, not guessed: `4.4M` currently on disk, covering roughly 15 days of history including two load-test bursts and 143 active series — linearly scaled to `90d`, that's on the order of 26MB. Padded 10x for cardinality/volume growth well beyond anything currently planned, still under 300MB. `5GB` sits more than an order of magnitude above that padded estimate. Under every growth scenario currently anticipated, `retention.time` is what actually prunes, and `retention.size` never binds — which is the only way a size cap and a portfolio-retention time window can coexist without the cap quietly undermining the window.

The written value and the effective one differ in name: the config file says `5GB`, and the running process reports its retention as `90d or 5GiB` — Prometheus reads the suffix as base-2, so the cap is about 5.37 × 10⁹ bytes rather than 5 × 10⁹. Immaterial at this margin, and recorded only so that the next reader comparing the file against `/api/v1/status/runtimeinfo` does not have to work out whether the difference means something.

### D3 — Existing data: not yet lost, and only saved by applying this promptly
Both clauses the brief for this change asks to be decided between apply, to different data:
- **"Raising retention before a block is deleted keeps it."** Checked live, re-confirmed at time of this revision: neither the 2026-08-12 nor the 2026-08-19 run's data has been dropped — both are still queryable. Applying this change (restarting `prometheus` with the new config) before Prometheus' own compaction drops the oldest block keeps everything currently in `prometheus_data`, including both runs.
- **"Nothing brings back a block already dropped."** Applies to nothing yet, as far as this proposal can observe — but it is why the timing in `proposal.md`'s Impact section is stated as urgent rather than routine. The oldest real data on disk (`2026-08-07`) is, as of this revision, exactly as old as the default retention window it's still running under. This proposal existing does not change that clock; only applying it does, and applying it is explicitly out of this proposal's scope.

No data has been migrated, exported, or otherwise protected by writing this document. The only thing that protects it is a restart this change does not perform.

## Risks / Trade-offs

- **[Risk]** The urgency in D3 is real but this proposal, by its own brief, cannot act on it — there is a window between this being written and this being applied during which the oldest data could still be dropped under the unmodified default. → **Mitigation**: stated plainly in `proposal.md` Impact rather than left implicit; the fix is prompt application, which is a follow-up action outside this change's scope, not a mitigation this change can perform itself.
- **[Risk]** `5GB` is padded well above measured growth on the assumption that current usage patterns are representative; a genuinely different future workload (e.g. much higher-frequency scraping, or a metrics change with high-cardinality labels) could exceed it sooner than D2's reasoning assumes. If it ever does, D2's mechanics apply: oldest data goes first, which for this stack means the size cap — not just the time bound — would start eating into the exact portfolio history D1 exists to keep. → **Mitigation**: none built into this change — re-measuring and re-deciding both values if the stack's usage pattern changes materially is future work, not automated here.
- **[Risk]** Using the config-file `storage.tsdb.retention` block instead of the deprecated flags is a departure from how this change was scoped, and could be judged the wrong call if there's a reason to prefer `docker-compose.yaml` visibility that this document doesn't have context on. → **Mitigation**: none beyond stating the evidence for the departure clearly (D0) so it can be overridden with full context if the reasoning doesn't hold up.

## Migration Plan

Config-only, additive: adds a `storage:` block to `observability/prometheus.yml`; nothing existing in that file changes. No data migration — the named volume `prometheus_data` is unaffected by the config change itself. Applying it is `docker-compose restart prometheus` (a process restart, not a recreate — no image, command, or compose-file field changes), which the scaffold's own `Restarting the stack preserves prior data` scenario already covers and already treats as safe for this exact volume. Rollback is reverting the config edit and restarting again; the only way to lose data is to leave the change unapplied past the point Prometheus' own compaction drops a block under the old default, per D3 — rollback afterward cannot undo that.

## Open Questions

- **Whether `5GB` should be revisited once `llm_call_duration_seconds`/`rag_retrieval_total` gain real recording call sites.** Not urgent — D2's padding already accounts for a 10x series-count increase — but worth a deliberate re-check rather than assuming the original number still holds indefinitely.
- **Whether this reasoning belongs anywhere Grafana-dashboard-adjacent** (e.g. a panel or note showing how close the stack is to either bound), so "quietly approaching the ceiling" doesn't become a second version of the exact problem this change fixes. Not proposed here — flagged for whoever next touches the dashboard.
