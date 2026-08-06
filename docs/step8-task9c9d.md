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

**Panels** — build exactly these six, in this order. The PromQL below was validated by hand
against the running stack; use it as given unless it errors.

1. **`/chat` p50 / p95 / p99 latency** (timeseries, unit `s`)
   Three queries, legends `p50` / `p95` / `p99`:
   ```
   histogram_quantile(0.50, sum by (le) (rate(chat_request_duration_seconds_bucket[5m])))
   histogram_quantile(0.95, sum by (le) (rate(chat_request_duration_seconds_bucket[5m])))
   histogram_quantile(0.99, sum by (le) (rate(chat_request_duration_seconds_bucket[5m])))
   ```
   This is the `docs/plan.md` "p50/p95/p99" requirement.

2. **p95 latency by intent** (timeseries, unit `s`, legend `{{intent}}`)
   ```
   histogram_quantile(0.95, sum by (le, intent) (rate(chat_request_duration_seconds_bucket[5m])))
   ```
   Add a panel description explaining the expected shape: `weather` should sit noticeably higher
   because `call_weather_tool` makes an extra LLM call to extract the city name before hitting
   Open-Meteo. This panel exists to make that cost visible.

3. **Request rate by intent** (timeseries, unit `reqps`, legend `{{intent}}`)
   ```
   sum by (intent) (rate(chat_request_duration_seconds_count[5m]))
   ```
   Panel description: this is the intent-distribution signal. Note that it comes from the
   histogram's `_count` series, which is why a separate intent counter would be redundant
   for distribution alone.

4. **Error rate** (timeseries, unit `percentunit`, legend `error ratio`)
   ```
   sum(rate(chat_request_duration_seconds_count{status="error"}[5m]))
     / sum(rate(chat_request_duration_seconds_count[5m]))
   ```
   Guard against the no-traffic case: with zero requests this is `0/0` and renders as `NaN`.
   Leave it as-is (do not wrap in `or vector(0)`) but say so in the panel description — an
   operator should know the difference between "no errors" and "no traffic".

5. **Intent classifier fallback rate** (timeseries, unit `percentunit`, legend `fallback ratio`)
   ```
   sum(rate(intent_classification_total{fallback="true"}[5m]))
     / sum(rate(intent_classification_total[5m]))
   ```
   Panel description: fraction of requests where the LLM returned something outside the
   `valid_intents` allowlist in `classify_intent` and was silently coerced to `"general"`.
   A rise here means classifier degradation, which the resolved-intent label alone cannot show.

6. **Declared-but-unrecorded instruments** (text panel, not a graph)
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
4. After running `scripts/generate_load.py`, each of the six dashboard queries returns
   non-empty data in the Prometheus expression browser. Record any that do not.
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
