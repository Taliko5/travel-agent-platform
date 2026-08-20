## 1. Carried over from `step8-observability-scaffold` Section 9

Moved verbatim on 2026-08-20. That section's heading described it as "reference only — not implemented by this change", which stopped being true once the counter-seeding fix, the Grafana dashboard and the load generator landed inside it. It is this change's subject matter. Restructuring, and the 9-d tasks, are added in a following step; nothing below has been reworded.

- [x] Define final metric names, label sets, and histogram bucket boundaries for the four key metrics; wire the actual `.record()`/`.add()` calls into the recording call sites marked in Section 5.
  - Partially done: `chat_request_duration_seconds` and `intent_classification_total` are recorded; `llm_call_duration_seconds` and `rag_retrieval_total` are declared but have no call sites, so they are absent from `/metrics` by design.
- **Fix counter seeding: instrument measurements taken at import time are silently discarded.**
  - Symptom, measured 2026-08-11: on a freshly restarted backend, `curl -s localhost:8000/metrics/ | grep "^# HELP"` returns only the ten default `python_*` / `process_*` series. No application metrics, and no `target_info`. A single `POST /chat` makes `chat_request_duration_seconds` and `intent_classification_total` appear. `rag_retrieval_total` never appears, despite `metrics.py:76` calling `rag_retrieval_count.add(0)` specifically to make it visible immediately.
  - Root cause: `backend/api/main.py:25` (`from agent.graph import build_graph`) transitively imports `observability.metrics` via `agent/graph.py:3` → `agent/nodes.py:9`. So `metrics.py` executes **before** `set_meter_provider()` at `main.py:53`. Instruments created without a real `MeterProvider` are OTel proxy instruments, and measurements recorded on a proxy before a provider is installed are dropped with no error. The proxies bind correctly once the provider is set, which is why runtime `.add()`/`.record()` calls work normally — only the import-time seeds are lost.
    - Reproduced against the pinned versions (`opentelemetry-sdk==1.43.0`, `opentelemetry-exporter-prometheus==0.64b0`, `prometheus-client==0.24.1`): a counter seeded *after* `set_meter_provider()` is exported; the identical counter seeded *before* it is not exported until a later real measurement.
    - The comment at `main.py:55-56` ("Imported after set_meter_provider so the instruments register against the configured MeterProvider") states an ordering guarantee that does not hold — line 57 re-imports an already-executed module and is a no-op. Reordering imports does not fix this: any import of the graph pulls `metrics.py` in first. Correct it or the next reader will trust it.
  - **Agreed fix — option (b): pre-seed the full label combinations, not a bare `.add(0)`.** The current seed passes no attributes, so even when it does execute it creates a single label-less series that matches neither `{fallback="true"}` nor any `by (intent)` grouping — it fails to achieve its purpose *and* adds an `intent=""` series to panel 3. Seed `VALID_INTENTS × fallback ∈ {"true","false"}` = 10 series at 0 instead, from a hook that runs after `set_meter_provider()`.
    - Hoist `valid_intents` out of `classify_intent` (`agent/nodes.py:22`, currently a function-local list) into a module constant so the seeding loop and the classifier share one definition. Adding an intent must not require updating two places.
    - Rationale for seeding at all: a counter that exists at 0 records a *starting point*. Without it, Prometheus first observes the series already at some value, and the increase up to that value is invisible to `rate()`. It also makes queries answer "0" (nothing has happened) instead of "No data" (unknown).
    - `rag_retrieval_total` is the opposite case, and the two must not be conflated. **Decided 2026-08-15: keep the bare label-less `.add(0)` for `rag_retrieval_total`** (moved into the post-provider hook with the rest, so it actually takes effect). A label-less seed is harmful for `intent_classification_total` because it manufactures an `intent=""` series that pollutes panel 3 — but `rag_retrieval_total` has no labels anywhere yet, no recording call sites, and no panel, so a label-less zero is a *truthful* statement that no retrieval has happened. That is precisely what seeding is for. Re-seed it with real label combinations when its recording call sites and label set are decided; until then the existing test assertion that it appears on `/metrics` stays as written.
  - **Confirmed in CI on 2026-08-15, not only locally.** On the `fix/step8-panel5-and-absent-metrics` PR, `test_observability.py::TestMetricsEndpoint::test_metrics_body_has_seeded_counters_not_histograms` fails at line 78, `assert "intent_classification_total" in body` — 1 failed, 76 passed.
    - The failure was latent, not absent. `.github/workflows/ci.yml` gates the backend lint/format/test steps behind a `dorny/paths-filter` check on `backend/**`, reporting success as a no-op when `backend/` is untouched. The 9-c dashboard change ran `ruff format backend/` under its Ground rules exception, which touched `backend/` and so actually ran the test job. **Every future change that touches `backend/` will hit this until it is fixed** — including the DNS/TLS work, which touches backend.
  - **The test is order-dependent and must be fixed alongside the application code.** Fixing the seeding is necessary but not sufficient:
    - The CI response body also contains `chat_request_duration_seconds_bucket{intent="chitchat",...} 3.0`, so `assert "chat_request_duration_seconds" not in body` (line 83) is *already* false. `/metrics` is process-global state, and `test_api_main.py::TestChatEndpoint` posts to `/chat` three times earlier in the same pytest session — the endpoint records the histogram even though `api.main.graph` is mocked. That assertion holds only when the file runs in isolation; today it is simply never reached, because line 78 fails first. Seed the counters and line 83 becomes the new failure.
    - Drop that assertion and record why in a comment. `assert "llm_call_duration_seconds" not in body` stays valid — nothing anywhere records it, so no test ordering can populate it.
  - Checklist for the fix:
    - [x] Move seeding out of import time: wrap it in a function in `metrics.py`, call it from `main.py` after `set_meter_provider(meter_provider)`. Reordering imports is not a fix.
    - [x] Hoist `valid_intents` from `classify_intent` (`agent/nodes.py`) into a module constant shared by the classifier and the seeding loop.
    - [x] Seed `VALID_INTENTS × fallback ∈ {"true","false"}` on `intent_classification_total` instead of a bare label-less `.add(0)`.
    - [x] Keep `rag_retrieval_total`'s bare label-less `.add(0)` (decision recorded above), just relocated into the post-provider hook. Do not give it invented labels.
    - [x] Remove the order-dependent `chat_request_duration_seconds not in body` assertion, with a comment explaining why.
    - [x] Correct the inaccurate ordering comment at `main.py:55-56`.
    - [x] `pytest backend/tests/ -v` green, and still green when `test_observability.py` is run on its own.
  - **Histograms must stay unseeded.** `metrics.py:67-74` is right: a fake `.record(0)` injects a permanent "one observation of 0 seconds" data point that skews `histogram_quantile()` and `rate(_sum)/rate(_count)` forever. This means `chat_request_duration_seconds{status="error"}` will not exist until a request actually fails, no matter how the counter question is settled — so the dashboard's error-rate PromQL must remain absence-tolerant regardless. Panels 4 and 5 of `travel-agent-overview.json` already wrap their numerators in `or vector(0)` for this reason, and should keep doing so even after this fix lands.
- **Re-tune `chat_request_duration_seconds` bucket boundaries** (blocked on nothing; deliberately excluded from the 9-c/9-d dashboard change because `backend/observability/metrics.py` is application code).
  - Evidence, measured 2026-08-11 over 127 requests via `sum by (le) (chat_request_duration_seconds_bucket)`:

    | `le` | cumulative | in that bucket |
    |---|---|---|
    | 0.5 / 1.0 / 1.5 / 2.0 / 3.0 / 5.0 | 0 | 0 |
    | 7.0 | 46 | 46 |
    | 10.0 | 121 | **75** |
    | 20.0 | 127 | 6 |
    | 60.0 / 120.0 / +Inf | 127 | 0 |

    Nine of twelve buckets are empty. Eight of the eleven boundaries sit where nothing has ever been observed, while the 7.0–10.0s region holding 75 of 127 observations is undivided. Consequently p50 (7.70s), p90 (9.73s) and p95 (9.99s) all resolve inside that one bucket — three cuts through a single linear interpolation, not three measurements.
  - Agreed replacement: `[0.5, 1.0, 2.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0, 20.0, 30.0, 60.0]` (11 boundaries → 14; ~120 → ~150 series at `intent` × `status` = 10 label combinations).
    - `0.5 / 1.0 / 2.0` are retained for the **error path**, not the success path. They are empty today because nothing has failed yet, not because fast requests do not exist; quota (429) and validation failures return in milliseconds.
    - `5.0`–`10.0` at 1s steps: 121 of 127 observations land here, so the resolution budget goes here. 1s is the floor — Gemini's run-to-run jitter is on the order of a second, and finer buckets would be false precision.
    - `12 / 15 / 20` subdivide the weather tail; `(10, 20]` currently holds 6 observations across a 10s-wide bucket, which is where p99's multi-second error comes from.
    - Dropped: `1.5` and `3.0` (no data, no rationale) and `120.0` (past 60s the request is already pathological; distinguishing 90s from 110s has no value, and `+Inf` still catches it).
  - Expected outcome: p50, p95 and p99 land in three *different* buckets, which is what does not happen today.
  - `llm_call_duration_seconds` currently copies these same boundaries verbatim. It must not copy the new ones either — it measures a *component* of a `/chat` request, so it needs its own values. Do not guess them: when wiring its recording call sites, start with a coarse log-spaced set (e.g. `[0.1, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20]`), measure the distribution the same way, then re-tune once.
  - Panel 6 of `travel-agent-overview.json` (latency distribution heatmap) exists to make this re-checkable after the change lands.
- Decide and apply real span names/attributes for the events `OTelCallbackHandler` (Section 4) receives (e.g. what request/response data belongs on the `classify_intent` chain span vs. the `generate_response` chain span vs. the nested LLM-call span within it).
- **9-c — Build Grafana dashboards** in `observability/grafana/dashboards/` visualizing `/chat` latency percentiles, intent distribution, LLM call duration, and RAG retrieval rate.
  - Full specification: **`docs/step8-task9c9d.md`**. That document is authoritative for the panel expressions, the panel descriptions, and the measurement figures quoted in them. Do not restate any of it here — the checklist below tracks progress only, and a second copy of the numbers is how the 2026-08-11 / 2026-08-12 discrepancy in this section arose.
  - [x] `scripts/generate_load.py` (Task 1) — recreated 2026-08-18 from the Task 1 specification in `docs/step8-task9c9d.md`. `rate()` needs several scrape intervals of data before the panels read as anything but broken, so this is a prerequisite for verifying any expression.
    - **This item previously read "committed", which was not true.** Checked 2026-08-18: neither `scripts/generate_load.py` nor the `scripts/` directory existed in the working tree, on any branch, or in either worktree under `.claude/worktrees/`, and `.gitignore` does not exclude them; the "Generating load" subsection Task 1 also requires in `docs/step8.md` was missing too. The 2026-08-12 load run did happen, so a generator existed at that time and was never landed in the repo. A `[x]` in this file is not evidence that the artefact it names is on disk — check.
  - [x] Verify all eight PromQL expressions in the Prometheus expression browser (panels 1–6; panel 1 contributes three) — all eight returned non-empty.
  - [x] `observability/grafana/dashboards/travel-agent-overview.json` (Task 2) — raw dashboard model, `uid: travel-agent-overview`, `id: null`, datasource referenced through a `${datasource}` template variable:
    - [x] Panel 1 — `/chat` p50 / p95 / p99, successful requests only (`status="ok"`), literal legends
    - [x] Panel 2 — p95 by intent; description quotes the `_sum / _count` figures, **not** the interpolated "19s"
    - [x] Panel 3 — request rate by intent, from the histogram's `_count` series
    - [x] Panel 4 — error rate; `or vector(0)` wraps the numerator only. **Expression frozen — verified against live data, not open for revision.**
    - [x] Panel 5 — intent classifier fallback rate; same numerator-only guard, same reason. **Expression frozen.**
    - [x] Panel 6 — latency distribution heatmap; `"format": "heatmap"` on the target and `"calculate": false` in panel options are both mandatory
    - [x] Panel 7 — text panel covering the declared-but-unrecorded instruments
  - [x] Update `observability/grafana/dashboards/README.md` to describe the dashboard that now exists and how to add more
  - [x] Confirm Grafana actually provisions the file (restart Grafana, then check its logs for the read from `/etc/grafana/dashboards` with no error)
  - **Scope of that confirmation, verified 2026-08-18.** The restart ran against a persisted `grafana_data` volume in which the dashboard was already present, and the provisioning cycle took 7ms (`starting to provision dashboards` at 15:43:54.676 → `finished to provision dashboards` at 15:43:54.683) — consistent with Grafana checksumming the file and skipping the write as unchanged. The decisive evidence was `GET /api/dashboards/uid/travel-agent-overview` returning `meta.provisioned: true` with `meta.provisionedExternalId: "travel-agent-overview.json"`, which proves the file provider owns this dashboard. It does **not** prove that a cold start against an empty `grafana_data` parses and loads the JSON successfully. That test requires `docker-compose down -v`, which also destroys `prometheus_data`; defer it until after the load re-run under 9-d, when the scraped data is expendable.
    - A single `level=error msg="failed to walk provisioned dashboards" error="index is closed"` at 15:43:11 appears in the same log window but is **not** part of the cycle above: it predates the restart's shutdown (`module stopped module=provisioning` at 15:43:45) and belongs to the previous six-day-old Grafana process, where a bleve search-index cache eviction (`index evicted from cache` reason=expired) raced the provider's 30s re-scan (`updateIntervalSeconds: 30`). It does not touch loading the file from disk. Do not re-investigate it. Separately, `logger=provisioning.plugins` and `logger=provisioning.alerting` log errors about missing `/etc/grafana/provisioning/plugins` and `/etc/grafana/provisioning/alerting` directories on every start — those provisioners are not configured for this stack and never were.
- **9-d — Get the pipeline showing real data end-to-end** via `docker-compose up` and debug any gaps (missing spans, empty Prometheus targets, no Grafana data, missing trace/log correlation) collaboratively rather than solo.
  - [ ] Tracked in Section 2 of this file. No longer blocked.
    - The host-network question is closed. `docs/step8-host-network.md` records what it turned out to be, and the one three-minute residual it could not explain. Do not restate any of it here.
- Evaluate whether LangSmith is worth adopting alongside or instead of the hand-rolled node spans.
- Scope and design actual CloudWatch log shipping as part of Step 9 (AWS Deployment), once an AWS account/log group exists to target — the structured JSON logging from Section 3 is the prep work for that.

## 2. 9-d — End-to-end verification

Full procedure: **`docs/step8-task9c9d.md`, Task 3** — eight numbered items. That document is authoritative; the checklist below tracks progress only. Do not restate the procedure here.

Preconditions, established 2026-08-19 and 2026-08-20, not to be re-litigated: the host-network question is closed (`docs/step8-host-network.md`), and the run to verify against is the controlled one of 2026-08-19 — 60 requests, 60 × HTTP 200, `caffeinate` confirmed to have held. The TSDB holds roughly 108 requests for that date because an earlier attempt was killed by tooling after about 48; the clean run is the window 09:11:37Z–09:24:03Z.

- [ ] Item 1 — `/metrics/` contents: which of the four declared instruments appear
- [ ] Item 2 — `/metrics` returns 307 and `/metrics/` returns 200
- [ ] Item 3 — Prometheus target `UP`; record the scrape interval actually in effect
- [ ] Item 4 — all eight panel queries return data (panels 1–6; panel 1 contributes three)
- [ ] Item 5 — Grafana renders the provisioned dashboard with populated panels
- [ ] Item 6 — trace/log correlation: the paired log lines of one request share a `trace_id`
- [ ] Item 7 — no FastAPI spans for `/health` or `/metrics` after roughly two minutes idle
- [ ] Item 8 — record, do not fix, the mixed JSON and plain-text log streams
- [ ] Write the observed results into a "Verified End-to-End" section of `docs/step8.md`

Verification is read-only. Do not re-run the load generator, do not change container configuration, and never run `docker-compose down -v` — `prometheus_data` still holds the 2026-08-12 run until roughly 2026-08-27.
