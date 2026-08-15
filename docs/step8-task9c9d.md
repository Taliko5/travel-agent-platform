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

- **Do not modify application code.** One exception: you may run
  `ruff format backend/` and let it fix the two pre-existing formatting violations —
  a missing trailing newline in `backend/api/main.py` and two over-length lines in
  `backend/observability/metrics.py`. Do **not** run `ruff check --fix`, and do not touch
  histogram bucket boundaries or any other application logic in either file. Before finishing,
  run `git diff` on those two files and confirm every changed line is whitespace-only — if it
  isn't, revert and stop. Beyond this exception, `backend/agent/`, `backend/api/`,
  `backend/observability/`, `backend/rag/`, `backend/mcp_servers/`, and `frontend/` are all out
  of scope here. This change adds a load-generation script, dashboard JSON, and documentation,
  plus that one whitespace-only formatting fix.
- Do not change dependency versions (this includes `ruff==0.15.20`, pinned in `ruff.toml` —
  do not upgrade it) or `docker-compose.yaml`.
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
- CLI arguments: `--requests` (default 60), `--concurrency` (default 1),
  `--delay` (seconds between requests per worker, default 6.0), `--base-url`
- **Rate limiting matters**: the backend calls the Gemini free tier, which has a
  requests-per-minute cap. Default settings must stay conservative. Document the risk in the
  script's module docstring and in `--help`.
  - These defaults are not arbitrary. `--concurrency 2 --delay 1.0` works out to ~120
    requests/minute, which the free tier rejects; the defaults above are ~10 requests/minute.
    That rate was run by hand on 2026-08-11 — 60 requests at 6s intervals, all `200`, no
    throttling — and it is what produced the 127-observation dataset the panel 6 bucket
    analysis is based on. Do not raise these defaults; `--delay` and `--concurrency` exist so
    a caller with a paid key can opt into more load explicitly.
  - A single run at these defaults takes about six minutes. Say so in `--help`, so nobody
    assumes the script has hung.
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

### Measurement provenance

Every figure quoted in the panel descriptions below comes from **one load run on 2026-08-12**:
60 requests at the `scripts/generate_load.py` defaults, read back from Prometheus' TSDB. They
replace an earlier set of 2026-08-11 figures, which were measured against a container instance
that no longer exists and could not be reproduced. Do not reinstate the old numbers.

Two caveats travel with these figures and must be repeated in any panel description that quotes
them:

- **The host's Docker networking was unhealthy during the run.** Six of the 60 requests failed
  with `httpx.ConnectError: Temporary failure in name resolution` and
  `[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate` on the backend's outbound call to
  Gemini. One retried inside `google_genai`'s tenacity loop for 1025.74s before giving up,
  because `backend/api/main.py` puts no deadline on `await graph.ainvoke(...)`. Prometheus' `up`
  series also has three genuine sample gaps (705s, 615s, and 1950s — the last well after the run
  had ended). Everything in the error tail — the `20.0`, `60.0` and `+Inf` buckets — therefore
  describes an infrastructure incident, not the application.
- **The 54 successful requests are unaffected.** Panels 1, 2 and 3 read the success path, and
  those figures are usable as they stand.

Quantiles are quoted below as ranges across the run rather than as single points. At this request
volume a `rate(...[5m])` window holds only ~20 observations, so the quantile moves as the window
slides, and a single request can relocate it into the next bucket.

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

   Do **not** add a p90 series. Measured 2026-08-12, p50 ranged 6.34–8.92s and p95 ranged
   9.53–19.0s across the run. The p50 range straddles the `5.0–7.0` and `7.0–10.0` buckets; the
   p95 range straddles `7.0–10.0` and `10.0–20.0`. Every quantile this panel can draw is a cut
   through one of two linear interpolations, so a fourth line would add a fourth cut, not a
   fourth measurement. See panel 6.

   The panel description must note that p99 is sample-sensitive. Measured 2026-08-12, p99 ranged
   9.91–19.8s. Its lower end is real — most successful requests cluster just under the `10.0`
   boundary. Its upper end is not: it comes entirely from two observations (12.18s and 13.15s)
   being interpolated across the 10s-wide `10.0–20.0` bucket. At 54 successful observations per
   run and roughly 20 per `rate()` window, p99 is decided by a single request. Small p99
   movements are not signal, and large ones may still be bucket-width artefacts rather than
   latency changes.

2. **p95 latency by intent — successful requests** (timeseries, unit `s`, legend `{{intent}}`)
   ```
   histogram_quantile(0.95, sum by (le, intent) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
   ```
   Same `{status="ok"}` reasoning as panel 1.

   Measured 2026-08-12, from `_sum / _count` rather than from a quantile: `weather` averaged
   8.60s per request (128.93s / 15), against 6.85s for `general` (82.21 / 12), 6.56s for
   `transportation` (98.41 / 15) and 6.54s for `hotel` (78.46 / 12). That is roughly **1.3x**,
   and the separation is real — the only two successful requests to exceed 10s (12.18s and
   13.15s) were both `weather`, and no other intent produced one. The likely cause is that
   `call_weather_tool` makes an extra LLM call to extract the city name before hitting
   Open-Meteo. Put the figures and the date in the panel description so the next reader can tell
   an observation from a prediction.

   **Do not quote a "weather p95 ≈ 19s" figure.** An earlier version of this document did, and it
   was an artefact rather than an observation: no `weather` request in the run took longer than
   13.15s. The number arises because `histogram_quantile` interpolates linearly inside a bucket
   and the boundaries jump from `10.0` straight to `20.0`. Per intent, a 5-minute window holds
   about five `weather` observations; if one exceeds 10s, the p95 rank is `0.95 × 5 = 4.75`,
   which falls between the cumulative counts at `le=10.0` (4) and `le=20.0` (5), so the result is
   interpolated as `10.0 + 0.75 × 10.0 = 17.5s` — the same answer whether the true value was
   12.2s or 19.9s.

   The panel will keep drawing `weather` in the 17–19s range for exactly this reason. The panel
   description must say that those values are bucket-width artefacts, that the real tail is
   ~13s, and that the honest per-intent comparison comes from `_sum / _count`. This is the
   clearest available demonstration of why panel 6 exists.

   Note also that the gap is in the *tail*, not the middle: of 60 observations, 52 came in under
   10s. Only 8 exceeded it, and 6 of those 8 were the failed requests described under
   "Measurement provenance" — not slow successes.

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
   (sum(rate(intent_classification_total{fallback="true"}[5m])) or vector(0))
     / sum(rate(intent_classification_total[5m]))
   ```
   Panel description: fraction of requests where the LLM returned something outside the
   `valid_intents` allowlist in `classify_intent` and was silently coerced to `"general"`.
   A rise here means classifier degradation, which the resolved-intent label alone cannot show.

   The numerator-only `or vector(0)` is the same fix as panel 4, for the same reason: until the
   classifier fails once, no series carries `fallback="true"`, so an unguarded numerator is an
   empty vector and the panel reads "No data" for as long as the classifier is healthy. A panel
   whose job is to show classifier degradation must not go blank when the classifier is fine.

   Apply this even if `intent_classification_total` is later pre-seeded across all label
   combinations (see `tasks.md` Section 9). The dashboard should not depend on an
   application-side invariant to render correctly.

   Same gap-vs-zero semantics as panel 4: a flat zero line means "requests classified, none fell
   back"; a gap means "no classification traffic in the window, ratio undefined". Describe it
   that way in the panel description rather than in terms of `NaN`.

6. **Latency distribution heatmap** (heatmap, y-axis unit `s`)
   ```
   sum by (le) (rate(chat_request_duration_seconds_bucket[5m]))
   ```
   This panel answers a different question from panels 1 and 2: not "how slow is it?" but
   "are the histogram bucket boundaries placed where the data actually is?"

   **This is not a hypothesis — it was measured 2026-08-12** and read back from Prometheus'
   TSDB. Over 60 requests, the cumulative bucket counts were:

   | `le` | cumulative | observations in that bucket |
   |---|---|---|
   | 0.5 / 1.0 / 1.5 / 2.0 / 3.0 / 5.0 | 0 | 0 |
   | 7.0 | 28 | 28 |
   | 10.0 | 52 | **24** |
   | 20.0 | 54 | 2 |
   | 60.0 | 59 | 5 |
   | 120.0 | 59 | 0 |
   | +Inf | 60 | 1 |

   Seven of the twelve buckets are empty. The six boundaries below 5.0s hold nothing at all,
   while 52 of the 60 observations — 87% — fall between 5.0s and 10.0s, a region
   `backend/observability/metrics.py` divides with a single boundary at 7.0.

   The tail is emptier than the table suggests. The five observations in `20.0–60.0` and the one
   past `120.0` are the failed requests described under "Measurement provenance", not application
   latency; on a healthy stack those buckets would be empty too. Meanwhile `10.0–20.0` — which
   holds the only two genuinely slow successes, at 12.18s and 13.15s — is ten seconds wide. That
   width alone is what makes `histogram_quantile` report those two requests as a p95 near 17.5s,
   and it is why an earlier version of this document asserted a "weather p95 ≈ 19s" that no
   request ever produced. See panel 2.

   The consequence is that p50 (measured range 6.34–8.92s) only ever crosses the `5.0–7.0` and
   `7.0–10.0` boundaries, while p95 (9.53–19.0s) and p99 (9.91–19.8s) are decided by which side
   of `10.0` one or two requests happen to land on. These are cuts through two linear
   interpolations, not independent measurements. Bucket placement therefore determines how much
   of panels 1 and 2 is real, and no other panel makes that visible.

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
   A short markdown note stating that `llm_call_duration_seconds` and `rag_retrieval_total` are
   declared in `backend/observability/metrics.py` but have no recording call sites yet, so they
   are absent from `/metrics`. Reference the remaining Section 9-a work. This prevents the next
   reader from filing "missing metrics" as a bug.

   Do not attribute their absence to "no seeding". `metrics.py` *does* call
   `rag_retrieval_count.add(0)`, and that seed is silently discarded — see `tasks.md` Section 9
   for the measured cause. The accurate statement is simply that these two instruments have no
   recording call sites.

   The note should also say that **no** application metric appears on `/metrics` until the first
   `/chat` request after a restart, for the same underlying reason. Someone checking a freshly
   restarted stack will otherwise conclude the instrumentation is broken.

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
   because neither has any recording call site yet (the unfinished Section 9-a work).

   **Run this check *after* item 4's load generation, not before.** Measured 2026-08-11: on a
   freshly restarted backend with no traffic, `/metrics` returns only the ten default
   `python_*` / `process_*` series — no application metrics and no `target_info`. The first
   `/chat` request makes `chat_request_duration_seconds` and `intent_classification_total`
   appear. Checking this item on a cold stack will fail for a reason that has nothing to do
   with what the item is testing.

   Do **not** attribute `rag_retrieval_total`'s absence to "no seeding": `metrics.py` does seed
   it with `.add(0)`, and the seed is discarded. Root cause and the agreed fix are recorded in
   `tasks.md` Section 9; it is application code and out of scope here. Record what you observe
   and move on.
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

1. `ruff check backend/` and `ruff format --check backend/` must pass. Getting there requires
   running `ruff format backend/` once, per the Ground rules exception above, which fixes the
   two pre-existing violations in `backend/api/main.py` and `backend/observability/metrics.py`
   (`scripts/generate_load.py` should also be formatted with ruff)
2. `cd backend && pytest tests/ -v` must pass — application logic is unchanged (the only
   backend edits are the whitespace-only `ruff format` fixes permitted above), so this is a
   regression check only
3. Update `observability/grafana/dashboards/README.md` to describe the dashboard that now
   exists and how to add more
4. Present a summary. **Do not commit.**
