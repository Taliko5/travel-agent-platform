# Step 8 — Section 9-c / 9-d (instructions for Claude Code)

Section 9 of `openspec/changes/step8-observability-scaffold/tasks.md` lists user-owned
follow-on work. This covers two of those items:

- **9-c**: Grafana dashboards in `observability/grafana/dashboards/`
- **9-d**: getting the pipeline showing real data end-to-end and recording what was verified

Sections 9-a (metric recording) is **partially done**: `chat_request_duration_seconds` and
`intent_classification_total` are wired; `llm_call_duration_seconds` and `rag_retrieval_total`
are declared but not yet recorded. Do **not** wire the remaining two in this change — they are
a separate step.

## Ground rules

- **Do not modify application code.** `backend/agent/`, `backend/api/`, `backend/observability/`,
  `backend/rag/`, `backend/mcp_servers/`, and `frontend/` are all out of scope here.
  This change adds a load-generation script, dashboard JSON, and documentation only.
- Do not change dependency versions or `docker-compose.yaml`.
- The Grafana dashboard provisioning path is already wired
  (`observability/grafana/provisioning/dashboards/default.yml` → `/etc/grafana/dashboards`,
  bind-mounted from `observability/grafana/dashboards/`). Drop-in JSON is picked up
  automatically — do not add new provisioning config.
- Keep `observability/grafana/dashboards/README.md`; update its text rather than deleting it.

---

## Task 1: Load-generation script

**Why**: PromQL `rate()` needs several scrape intervals of data before it produces anything
readable. Hand-issued `curl` calls produce a handful of points and near-zero rates, which makes
the dashboard look broken when it isn't.

**Create** `scripts/generate_load.py` (create the `scripts/` directory).

Requirements:

- Send `POST /chat` requests against a configurable base URL (default `http://localhost:8000`)
- Cycle through prompts that exercise **all four routing branches** in
  `backend/agent/graph.py`'s `route_by_intent`, so every `intent` label value shows up:
  - `weather` → `call_weather_tool` (e.g. "What is the weather in Fukuoka?")
  - `transportation` + a flight keyword → `call_flight_tool` (e.g. "Cheap flights to Riga")
  - `hotel` → `call_hotel_tool` (e.g. "Find me a hotel in Lima")
  - `general` → `retrieve_context` (e.g. "What should I know before visiting Abu Dhabi?")
  - Include at least two prompt variants per branch so the data isn't perfectly uniform
- CLI arguments: `--requests` (default 40), `--concurrency` (default 2),
  `--delay` (seconds between requests per worker, default 1.0), `--base-url`
- **Rate limiting matters**: the backend calls the Gemini free tier, which has a
  requests-per-minute cap. Default settings must stay conservative. Document the risk in the
  script's module docstring and in `--help`.
- Print a running summary: per-intent counts, HTTP status counts, min/mean/max client-observed
  latency, and total wall-clock time. On any non-200 response, print the status and body so
  quota errors are obvious rather than silently skewing the metrics.
- Use only the standard library plus `httpx` (already in `backend/requirements.txt`).
  Do not add a new dependency.
- The script runs on the host against the compose stack, not inside a container.

Also add a short "Generating load" subsection to `docs/step8.md` under "Running Locally"
showing the command.

---

## Task 2: Grafana dashboard JSON

**Create** `observability/grafana/dashboards/travel-agent-overview.json`.

**Important**: this must be a raw Grafana dashboard JSON model suitable for file provisioning —
**not** an API "dashboard wrapper" object. Concretely:

- Top level is the dashboard model itself (`title`, `panels`, `templating`, `time`, ...),
  not `{"dashboard": {...}}`
- Set `"uid"` to a stable value (e.g. `travel-agent-overview`) so the dashboard keeps its URL
  across restarts
- Set `"id": null`
- Do **not** hardcode a datasource UID. Provisioned dashboards should reference the datasource
  by a template variable or by type. Add a `templating` variable of type `datasource`
  (query `prometheus`, name `datasource`) and have every panel target
  `{"type": "prometheus", "uid": "${datasource}"}`. Hardcoding a UID is the most common reason
  a provisioned dashboard renders "Datasource not found".
- `"schemaVersion"` should be a recent value (39 or higher)

**Panels** — build exactly these seven, in this order.

The PromQL below is a design proposal, not verified output. It has **not** been run against a
live stack. One earlier version of it (panel 4) was wrong in a way that is invisible when
reading the expression and only appears once real data exists. Treat the rest with the same
suspicion.

Before accepting each expression, run it in the Prometheus expression browser
(`http://localhost:9090/graph`) against a stack that has had `scripts/generate_load.py` run
against it, and confirm it returns a non-empty result. Record the outcome per panel as part of
Task 3, item 4.

If an expression returns nothing, do **not** silently substitute one of your own. Report which
panel failed, what the query returned, what you think the cause is, and your proposed
replacement — then stop and wait.

Panel 4 is the exception: its expression and its `or vector(0)` placement have already been
reasoned through and are not open for revision. Verify it returns data; do not redesign it.

1. **`/chat` p50 / p95 / p99 latency — successful requests** (timeseries, unit `s`)
   Three queries, legends `p50` / `p95` / `p99`:
   ```
   histogram_quantile(0.50, sum by (le) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
   histogram_quantile(0.95, sum by (le) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
   histogram_quantile(0.99, sum by (le) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
   ```
   This is the `docs/plan.md` "p50/p95/p99" requirement.

   The `{status="ok"}` filter is deliberate. Without it, a fast-failing outage — quota errors
   returning in milliseconds — drags every quantile *down*, so the panel reports an improvement
   at the exact moment the service breaks. Panel 4 owns "is it broken"; this panel owns "how slow
   is the working path". The cost is that slow failures (timeouts) disappear from this panel.
   That is accepted: panel 4 still counts them.

   Legends are literal strings, not `{{...}}`. `sum by (le)` leaves only `le` and
   `histogram_quantile` then consumes it, so the result carries no labels at all — there is
   nothing for `{{...}}` to interpolate.

   Do **not** add a p90 series. Measured on 2026-08-11, p50 (7.70s), p90 (9.73s) and p95 (9.99s)
   all resolve inside the same `7.0–10.0` bucket, so a fourth line would be a fourth cut through
   one linear interpolation, carrying no additional information. See panel 6.

   The panel description must note that p99 is sample-sensitive: at the request volumes this
   project generates (~127 observations per load run) p99 is decided by the second-slowest single
   request and currently resolves inside a 10s-wide bucket. Small p99 movements are not signal.

2. **p95 latency by intent — successful requests** (timeseries, unit `s`, legend `{{intent}}`)
   ```
   histogram_quantile(0.95, sum by (le, intent) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
   ```
   Same `{status="ok"}` reasoning as panel 1.

   Measured on 2026-08-11: `weather` p95 ≈ 19s, the other three intents ≈ 9–10s. This is an
   observation, not a prediction — put the figures and the date in the panel description so the
   next reader can tell the difference. The cause is that `call_weather_tool` makes an extra LLM
   call to extract the city name before hitting Open-Meteo, and that call shows up as roughly a
   doubling.

   Note that the gap is in the *tail*, not the middle: only 6 of 127 observations exceeded 10s
   overall, so weather's median also sits under 10s. It is weather's p95 that separates.

3. **Request rate by intent** (timeseries, unit `reqps`, legend `{{intent}}`)
   ```
   sum by (intent) (rate(chat_request_duration_seconds_count[5m]))
   ```
   Panel description: this is the intent-distribution signal. Note that it comes from the
   histogram's `_count` series, which is why a separate intent counter would be redundant
   for distribution alone.

4. **Error rate** (timeseries, unit `percentunit`, legend `error ratio`)
   ```
   (sum(rate(chat_request_duration_seconds_count{status="error"}[5m])) or vector(0))
     / sum(rate(chat_request_duration_seconds_count[5m]))
   ```
   The `or vector(0)` wraps the **numerator only**. Use the expression exactly as written —
   this placement is the whole point of the panel, and both "obvious simplifications" are wrong:

   - Dropping `or vector(0)` entirely breaks the healthy case. `status` is only ever recorded
     as `ok` or `error` (`backend/api/main.py`), and Prometheus does not create a series for a
     label value that has never occurred. On a stack that has never errored,
     `{status="error"}` does not exist, the numerator is an empty vector, and the whole
     division yields nothing — the panel reads "No data" during normal operation, which is the
     worst possible rendering for an error-rate panel.
   - Wrapping the *whole* expression in `or vector(0)` instead would flatten the no-traffic
     case to `0`, asserting "0% errors" when in fact nothing was measured.

   The intended semantics are **gap vs. zero**, not `NaN` vs. "No data" (Grafana renders both
   of the latter as the same gap in the line, so `NaN` on its own carries no signal a reader
   can see):

   - traffic flowing, no errors → `0 / 0.5 = 0`, a flat zero line. The ratio is computable and
     it really is zero.
   - no traffic → `0 / 0 = NaN`, drawn as a gap. The ratio is genuinely undefined and the panel
     should not claim otherwise.

   Write the panel `description` to say this in one or two sentences — that a gap means "no
   traffic in the window, ratio undefined" and a zero line means "requests served, none
   failed". Do not describe it in terms of `NaN`; describe what the reader sees.

   (An equivalent form that returns a true empty vector instead of `NaN` is to filter the
   denominator with `> 0`. It renders identically and is harder to read, so it is not used.)

5. **Intent classifier fallback rate** (timeseries, unit `percentunit`, legend `fallback ratio`)
   ```
   sum(rate(intent_classification_total{fallback="true"}[5m]))
     / sum(rate(intent_classification_total[5m]))
   ```
   Panel description: fraction of requests where the LLM returned something outside the
   `valid_intents` allowlist in `classify_intent` and was silently coerced to `"general"`.
   A rise here means classifier degradation, which the resolved-intent label alone cannot show.

6. **Latency distribution heatmap** (heatmap, y-axis unit `s`)
   ```
   sum by (le) (rate(chat_request_duration_seconds_bucket[5m]))
   ```
   This panel answers a different question from panels 1 and 2: not "how slow is it?" but
   "are the histogram bucket boundaries placed where the data actually is?"

   **This is not a hypothesis — it was measured on 2026-08-11.** Over 127 requests, the
   cumulative bucket counts were:

   | `le` | cumulative | observations in that bucket |
   |---|---|---|
   | 0.5 / 1.0 / 1.5 / 2.0 / 3.0 / 5.0 | 0 | 0 |
   | 7.0 | 46 | 46 |
   | 10.0 | 121 | **75** |
   | 20.0 | 127 | 6 |
   | 60.0 / 120.0 / +Inf | 127 | 0 |

   Nine of the twelve buckets are empty. `backend/observability/metrics.py` spends eight of its
   eleven boundaries below 5.0s or above 20.0s, where nothing has ever been observed, and leaves
   the 7.0–10.0s region — which holds 75 of 127 observations — undivided.

   The consequence is that p50 (7.70s), p90 (9.73s) and p95 (9.99s) all resolve inside that same
   single bucket. They are three cuts through one linear interpolation, not three measurements.
   Bucket placement therefore determines how much of panels 1 and 2 is real, and no other panel
   makes that visible.

   Do **not** re-tune the boundaries in this change — `metrics.py` is application code and is out
   of scope per the ground rules. Retuning is tracked separately, together with the remaining
   Section 9-a work (`llm_call_duration_seconds` copies the same boundaries verbatim, and it
   measures a *component* of these durations, so it needs its own values). This panel exists so
   the new boundaries can be re-checked after that change lands, without anyone having to
   remember to run an ad-hoc query.

   JSON requirements — these are the ways this panel is normally built wrong:

   - The target must set `"format": "heatmap"` (Prometheus datasource option). This is what makes
     the datasource sort series by `le` and convert Prometheus' **cumulative** buckets into the
     per-bucket counts a heatmap needs. Omit it and the panel still renders — as a plausible
     looking picture where every row above the data is darker than the one below it. It is wrong
     and it does not look wrong.
   - `"legendFormat": "{{le}}"`
   - Range query, not instant (`"instant": false`)
   - Panel `options` must set `"calculate": false`. The bucketing is already done server-side;
     letting Grafana recalculate buckets from the series values produces nonsense.
   - y-axis unit `s`

   State in the panel description what the reader is looking for: rows that never take on colour
   are wasted boundaries, and a single dark row holding most observations means that region needs
   to be subdivided.

7. **Declared-but-unrecorded instruments** (text panel, not a graph)
   A short markdown note stating that `llm_call_duration_seconds` and `rag_retrieval_total`
   are declared in `backend/observability/metrics.py` but have no recording call sites yet, so
   they are absent from `/metrics` by design. Reference the remaining Section 9-a work.
   This prevents the next reader from filing "missing metrics" as a bug.

**Dashboard-level settings**: default time range `now-1h`, refresh `30s`,
tags `["travel-agent", "step8"]`, timezone `browser`.

**Validation**: after writing the file, verify it parses as JSON and that every panel's
`targets[].expr` is non-empty. Then confirm Grafana actually loaded it:

```bash
docker-compose restart grafana
docker-compose logs grafana | grep -i -E "provisioning|dashboard"
```

Look for the dashboard being read from `/etc/grafana/dashboards` with no error. A JSON parse
failure or a schema problem shows up here, not in the UI.

---

## Task 3: Record the 9-d end-to-end verification

Add a **"Verified End-to-End"** section to `docs/step8.md`, and check off the corresponding
items in `openspec/changes/step8-observability-scaffold/tasks.md` Section 9.

Run through the following against a live `docker-compose up --build` stack and record the
**actual observed result** for each — not the expected one. If something does not work, write
down what actually happened and what you changed to fix it (config only; application code is
out of scope per the ground rules — if the fix requires touching application code, stop and
report instead).

1. `curl -s localhost:8000/metrics/` returns 200 and contains
   `chat_request_duration_seconds_bucket` and `intent_classification_total`.
   Confirm `llm_call_duration_seconds` and `rag_retrieval_total` are **absent** — expected,
   per Fix 1 (no seeding) and the unfinished Section 9-a work.
2. `curl -s -o /dev/null -w '%{http_code}' localhost:8000/metrics` returns `307`
   (no trailing slash), and `localhost:8000/metrics/` returns `200`.
   Note in the docs that `observability/prometheus.yml` uses `metrics_path: /metrics` and
   relies on Prometheus following the redirect.
3. `http://localhost:9090/targets` shows job `travel-agent-backend` as `UP`.
   Record the scrape interval actually in effect.
4. After running `scripts/generate_load.py`, every query on panels 1–6 returns non-empty data in
   the Prometheus expression browser (panel 7 is a text panel and has no query). That is eight
   queries in total, since panel 1 has three. Record any that do not return data.
5. Grafana at `http://localhost:3001` shows the provisioned dashboard with populated panels.
6. **Trace/log correlation**: pick one `/chat` request and confirm its log lines carry a
   non-null `trace_id`. Verify the two log lines emitted by the same request
   (`"chat request received"` and `"chat request completed"`) share the same `trace_id`:
   ```bash
   docker-compose logs backend | grep '"trace_id"' | tail -20
   ```
   Also confirm the `"chat request completed"` line carries `intent`, `status`, and
   `duration_seconds`.
7. **Span exclusion (Fix 5)**: confirm no FastAPI spans are emitted for `/health` or `/metrics`.
   Let the stack idle for ~2 minutes with no traffic and check that
   `docker-compose logs backend --since 2m` shows no new HTTP spans for those paths.
8. **Known gap to record, not fix**: `docker-compose logs backend` mixes JSON application logs
   with uvicorn's plain-text access logs, because `uvicorn.access` / `uvicorn.error` have
   `propagate=False` and their own handlers. Note this in the docs as an open item for Step 9's
   CloudWatch log shipping, since line-oriented JSON is the premise there.

---

## Wrap-up

1. `ruff check backend/` and `ruff format --check backend/` must pass
   (`scripts/generate_load.py` should also be formatted with ruff)
2. `cd backend && pytest tests/ -v` must pass — no application code changed, so this is a
   regression check only
3. Update `observability/grafana/dashboards/README.md` to describe the dashboard that now
   exists and how to add more
4. Present a summary. **Do not commit.**
