## 1. Dependencies

- [x] 1.1 Add `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-prometheus` (paired with the already-pinned `opentelemetry-sdk==1.43.0`), and a JSON log formatter (e.g. `python-json-logger`) to `backend/requirements.txt`, pinned consistently with existing `opentelemetry-*` versions.
- [x] 1.2 `pip install -r backend/requirements.txt` in the backend venv and confirm no version conflicts.

## 2. FastAPI + OTel SDK Wiring

- [x] 2.1 In `backend/api/main.py`, initialize a `TracerProvider` and `MeterProvider` at module load, constructed with a `Resource` carrying `service.name=travel-agent-backend`, `service.version` (reused from the FastAPI `app`'s existing `version="0.1.0"`), and `deployment.environment` (env var, default `local`).
- [x] 2.2 Wire the trace exporter to read `OTEL_EXPORTER_OTLP_ENDPOINT` from the environment: use `OTLPSpanExporter` when set, `ConsoleSpanExporter` when unset.
- [x] 2.3 Apply `FastAPIInstrumentor.instrument_app(app)` so inbound HTTP requests produce spans automatically.
- [x] 2.4 Add a `/metrics` route by wiring `opentelemetry.exporter.prometheus.PrometheusMetricReader` into the `MeterProvider` and mounting `prometheus_client.make_asgi_app()` (via `app.mount`) so the reader's registered instruments are exposed in Prometheus text-format output.
- [x] 2.5 Confirm `backend/tests/test_api_main.py` still passes unmodified — the OTel wiring must not require `graph` to be un-patchable or add new required env vars at import time.

## 3. Structured Logging with Trace Correlation

- [x] 3.1 Add `backend/observability/logging.py` configuring the stdlib root logger with a JSON formatter and a `logging.Filter` that reads `trace.get_current_span().get_span_context()` and attaches `trace_id`/`span_id` fields to each `LogRecord` (empty/null when no span is active).
- [x] 3.2 Call the logging setup from `backend/api/main.py` at startup, alongside the OTel SDK wiring from Section 2.
- [x] 3.3 Confirm a log emitted during a `/chat` request includes non-empty `trace_id`/`span_id`, and a log emitted at startup (before any request) doesn't raise even with no active span.

## 4. LangGraph/LangChain Span Instrumentation via Callback Handler

- [x] 4.1 Add `backend/observability/callback_handler.py` defining `OTelCallbackHandler(BaseCallbackHandler)` that starts a span in `on_chain_start`/`on_llm_start`/`on_tool_start` and ends it in the matching `on_chain_end`/`on_llm_end`/`on_tool_end` (success) or `on_chain_error`/`on_llm_error`/`on_tool_error` (failure) callback — leave real span attribute decisions as a `# TODO (user)` comment.
- [x] 4.2 Register `OTelCallbackHandler()` once via `config={"callbacks": [...]}` on the `graph.ainvoke(...)` call in `backend/api/main.py`. Do not modify `backend/agent/graph.py`; `backend/agent/nodes.py` is expected to need no changes either, but that's unverified until task 4.4.
- [x] 4.3 Confirm `backend/tests/test_graph_routing.py` still passes unmodified — since `graph.py` isn't touched, this should be a non-issue, but verify directly rather than assuming.
- [x] 4.4 During the Section 7.5 `docker-compose up` smoke test, verify with a real `/chat` request that `on_llm_start`/`on_llm_end` fire for the LLM call inside `generate_response`/`classify_intent` and produce a nested span under the node-level span. If they don't fire automatically, add `config: RunnableConfig` to both node function signatures in `backend/agent/nodes.py` and forward it to `get_model().invoke(prompt, config=config)`, then re-verify. Update `docs/step8.md` (Section 8.1) to describe whichever behavior was actually observed, not the assumed one.
      - Verified: sent a real `/chat` weather request against the docker-compose stack. Console span output showed `ChatGoogleGenerativeAI` spans nested directly under `call_weather_tool` and `generate_response` node spans (which are nested under a `LangGraph` span, itself under the FastAPI `POST /chat` span) — propagation works automatically via `config={"callbacks": [...]}` alone. No `nodes.py` changes were needed; the optimistic case held.

## 5. Placeholder Metric Instruments

- [x] 5.1 Add `backend/observability/metrics.py` declaring four named instruments: a histogram for `/chat` latency, a counter for intent distribution, a histogram for LLM call duration, and a counter/histogram for RAG retrieval rate — instruments only, no recording call sites, no bucket boundaries decided.
- [x] 5.2 Mark each instrument with a `# TODO (user): define labels/buckets and add .record()/.add() calls` comment pointing at the specific node(s) or route where it would be recorded.
- [x] 5.3 Confirm `/metrics` still returns `200` with these instruments present (even with zero recorded data points).

## 6. Instrumentation Tests

- [x] 6.1 Add `backend/tests/test_observability.py` with a test asserting `GET /metrics` returns `200` and the response body contains the four instrument names declared in Section 5.
- [x] 6.2 Add a test asserting `OTelCallbackHandler` from Section 4 ends its span on both the success path (`on_chain_end`/`on_llm_end`/`on_tool_end`) and the failure path (`on_chain_error`/`on_llm_error`/`on_tool_error`), invoking the handler's callbacks directly rather than requiring a real graph run.

## 7. Docker Compose: Prometheus + Grafana

- [x] 7.1 Create `observability/prometheus.yml` with a scrape config targeting the `backend` service's `/metrics` endpoint on the compose network.
- [x] 7.2 Create `observability/grafana/provisioning/datasources/prometheus.yml` provisioning a Grafana datasource pointing at the compose `prometheus` service.
- [x] 7.3 Create an empty `observability/grafana/dashboards/` directory (with a placeholder `README.md` noting dashboards are the user's hands-on task) and wire it as a Grafana dashboard-provisioning path so drop-in dashboard JSON is picked up automatically later.
- [x] 7.4 Add `prometheus` and `grafana` services to `docker-compose.yaml`, mounting the config/provisioning files above, with named volumes (`prometheus_data`, `grafana_data`) for persistent storage, healthchecks mirroring the existing `backend` service's pattern, exposing Prometheus on `9090` and Grafana on `3001` (avoiding the frontend's `3000`), with no `depends_on` from `backend`/`frontend`.
- [x] 7.5 Run `docker-compose up --build`, confirm all four services start and report healthy, and confirm Prometheus's target page shows the backend as reachable (verify by hitting `/metrics` directly first if the target shows "down").
- [x] 7.6 Confirm `docker-compose restart prometheus grafana` preserves previously scraped data (vs. `docker-compose down -v`, which is documented as the explicit reset path).

## 8. Documentation

- [x] 8.1 Write first-draft `docs/step8.md`: what's instrumented (resource-attributed FastAPI spans, `OTelCallbackHandler`-based LangGraph/LLM/tool spans, `/metrics`, structured/correlated logging, Prometheus/Grafana services with persistence), why (ties back to the four key metrics named in `docs/plan.md`), and how to run the stack locally. Describe the callback-handler mechanism (registered once at graph-invocation time in `main.py`) rather than a per-node wrapper.
- [x] 8.2 In `docs/step8.md`, add a clearly marked section listing what's scaffolded vs. what the user still owns (metric label/bucket design, span naming/attributes, Grafana dashboards, CloudWatch log-shipping/Step 9 follow-up), matching the division of labor from the proposal.
- [x] 8.3 In `docs/step8.md`, note LangSmith (already an installed transitive dependency via `langchain`) as an alternative/complementary LangGraph-native tracing option worth the user's own evaluation — mention it's also a `BaseCallbackHandler` and can be registered alongside `OTelCallbackHandler` for side-by-side comparison — and note `OTEL_EXPORTER_OTLP_ENDPOINT` as the path to a real trace backend later.
- [x] 8.4 Add `docs/step8.md` to the docs index/links in `CLAUDE.md`'s Docs section, following the existing `docs/step4.md`-style one-line entries.

## 9. User-Owned Follow-On Work (reference only — not implemented by this change)

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
    - `rag_retrieval_total` cannot be seeded meaningfully yet — its label set is still undecided. Seed it when its recording call sites are added.
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
- Build Grafana dashboards in `observability/grafana/dashboards/` visualizing `/chat` latency percentiles, intent distribution, LLM call duration, and RAG retrieval rate.
- Get the pipeline showing real data end-to-end via `docker-compose up` and debug any gaps (missing spans, empty Prometheus targets, no Grafana data, missing trace/log correlation) collaboratively rather than solo.
- Evaluate whether LangSmith is worth adopting alongside or instead of the hand-rolled node spans.
- Scope and design actual CloudWatch log shipping as part of Step 9 (AWS Deployment), once an AWS account/log group exists to target — the structured JSON logging from Section 3 is the prep work for that.
