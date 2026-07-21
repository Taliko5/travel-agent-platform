## 1. Dependencies

- [ ] 1.1 Add `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-prometheus` (paired with the already-pinned `opentelemetry-sdk==1.43.0`), and a JSON log formatter (e.g. `python-json-logger`) to `backend/requirements.txt`, pinned consistently with existing `opentelemetry-*` versions.
- [ ] 1.2 `pip install -r backend/requirements.txt` in the backend venv and confirm no version conflicts.

## 2. FastAPI + OTel SDK Wiring

- [ ] 2.1 In `backend/api/main.py`, initialize a `TracerProvider` and `MeterProvider` at module load, constructed with a `Resource` carrying `service.name=travel-agent-backend`, `service.version` (reused from the FastAPI `app`'s existing `version="0.1.0"`), and `deployment.environment` (env var, default `local`).
- [ ] 2.2 Wire the trace exporter to read `OTEL_EXPORTER_OTLP_ENDPOINT` from the environment: use `OTLPSpanExporter` when set, `ConsoleSpanExporter` when unset.
- [ ] 2.3 Apply `FastAPIInstrumentor.instrument_app(app)` so inbound HTTP requests produce spans automatically.
- [ ] 2.4 Add a `/metrics` route by wiring `opentelemetry.exporter.prometheus.PrometheusMetricReader` into the `MeterProvider` and mounting `prometheus_client.make_asgi_app()` (via `app.mount`) so the reader's registered instruments are exposed in Prometheus text-format output.
- [ ] 2.5 Confirm `backend/tests/test_api_main.py` still passes unmodified — the OTel wiring must not require `graph` to be un-patchable or add new required env vars at import time.

## 3. Structured Logging with Trace Correlation

- [ ] 3.1 Add `backend/observability/logging.py` configuring the stdlib root logger with a JSON formatter and a `logging.Filter` that reads `trace.get_current_span().get_span_context()` and attaches `trace_id`/`span_id` fields to each `LogRecord` (empty/null when no span is active).
- [ ] 3.2 Call the logging setup from `backend/api/main.py` at startup, alongside the OTel SDK wiring from Section 2.
- [ ] 3.3 Confirm a log emitted during a `/chat` request includes non-empty `trace_id`/`span_id`, and a log emitted at startup (before any request) doesn't raise even with no active span.

## 4. LangGraph/LangChain Span Instrumentation via Callback Handler

- [ ] 4.1 Add `backend/observability/callback_handler.py` defining `OTelCallbackHandler(BaseCallbackHandler)` that starts a span in `on_chain_start`/`on_llm_start`/`on_tool_start` and ends it in the matching `on_chain_end`/`on_llm_end`/`on_tool_end` (success) or `on_chain_error`/`on_llm_error`/`on_tool_error` (failure) callback — leave real span attribute decisions as a `# TODO (user)` comment.
- [ ] 4.2 Register `OTelCallbackHandler()` once via `config={"callbacks": [...]}` on the `graph.ainvoke(...)` call in `backend/api/main.py`. Do not modify `backend/agent/graph.py`; `backend/agent/nodes.py` is expected to need no changes either, but that's unverified until task 4.4.
- [ ] 4.3 Confirm `backend/tests/test_graph_routing.py` still passes unmodified — since `graph.py` isn't touched, this should be a non-issue, but verify directly rather than assuming.
- [ ] 4.4 During the Section 7.5 `docker-compose up` smoke test, verify with a real `/chat` request that `on_llm_start`/`on_llm_end` fire for the LLM call inside `generate_response`/`classify_intent` and produce a nested span under the node-level span. If they don't fire automatically, add `config: RunnableConfig` to both node function signatures in `backend/agent/nodes.py` and forward it to `get_model().invoke(prompt, config=config)`, then re-verify. Update `docs/step8.md` (Section 8.1) to describe whichever behavior was actually observed, not the assumed one.

## 5. Placeholder Metric Instruments

- [ ] 5.1 Add `backend/observability/metrics.py` declaring four named instruments: a histogram for `/chat` latency, a counter for intent distribution, a histogram for LLM call duration, and a counter/histogram for RAG retrieval rate — instruments only, no recording call sites, no bucket boundaries decided.
- [ ] 5.2 Mark each instrument with a `# TODO (user): define labels/buckets and add .record()/.add() calls` comment pointing at the specific node(s) or route where it would be recorded.
- [ ] 5.3 Confirm `/metrics` still returns `200` with these instruments present (even with zero recorded data points).

## 6. Instrumentation Tests

- [ ] 6.1 Add `backend/tests/test_observability.py` with a test asserting `GET /metrics` returns `200` and the response body contains the four instrument names declared in Section 5.
- [ ] 6.2 Add a test asserting `OTelCallbackHandler` from Section 4 ends its span on both the success path (`on_chain_end`/`on_llm_end`/`on_tool_end`) and the failure path (`on_chain_error`/`on_llm_error`/`on_tool_error`), invoking the handler's callbacks directly rather than requiring a real graph run.

## 7. Docker Compose: Prometheus + Grafana

- [ ] 7.1 Create `observability/prometheus.yml` with a scrape config targeting the `backend` service's `/metrics` endpoint on the compose network.
- [ ] 7.2 Create `observability/grafana/provisioning/datasources/prometheus.yml` provisioning a Grafana datasource pointing at the compose `prometheus` service.
- [ ] 7.3 Create an empty `observability/grafana/dashboards/` directory (with a placeholder `README.md` noting dashboards are the user's hands-on task) and wire it as a Grafana dashboard-provisioning path so drop-in dashboard JSON is picked up automatically later.
- [ ] 7.4 Add `prometheus` and `grafana` services to `docker-compose.yaml`, mounting the config/provisioning files above, with named volumes (`prometheus_data`, `grafana_data`) for persistent storage, healthchecks mirroring the existing `backend` service's pattern, exposing Prometheus on `9090` and Grafana on `3001` (avoiding the frontend's `3000`), with no `depends_on` from `backend`/`frontend`.
- [ ] 7.5 Run `docker-compose up --build`, confirm all four services start and report healthy, and confirm Prometheus's target page shows the backend as reachable (verify by hitting `/metrics` directly first if the target shows "down").
- [ ] 7.6 Confirm `docker-compose restart prometheus grafana` preserves previously scraped data (vs. `docker-compose down -v`, which is documented as the explicit reset path).

## 8. Documentation

- [ ] 8.1 Write first-draft `docs/step8.md`: what's instrumented (resource-attributed FastAPI spans, `OTelCallbackHandler`-based LangGraph/LLM/tool spans, `/metrics`, structured/correlated logging, Prometheus/Grafana services with persistence), why (ties back to the four key metrics named in `docs/plan.md`), and how to run the stack locally. Describe the callback-handler mechanism (registered once at graph-invocation time in `main.py`) rather than a per-node wrapper.
- [ ] 8.2 In `docs/step8.md`, add a clearly marked section listing what's scaffolded vs. what the user still owns (metric label/bucket design, span naming/attributes, Grafana dashboards, CloudWatch log-shipping/Step 9 follow-up), matching the division of labor from the proposal.
- [ ] 8.3 In `docs/step8.md`, note LangSmith (already an installed transitive dependency via `langchain`) as an alternative/complementary LangGraph-native tracing option worth the user's own evaluation — mention it's also a `BaseCallbackHandler` and can be registered alongside `OTelCallbackHandler` for side-by-side comparison — and note `OTEL_EXPORTER_OTLP_ENDPOINT` as the path to a real trace backend later.
- [ ] 8.4 Add `docs/step8.md` to the docs index/links in `CLAUDE.md`'s Docs section, following the existing `docs/step4.md`-style one-line entries.

## 9. User-Owned Follow-On Work (reference only — not implemented by this change)

- Define final metric names, label sets, and histogram bucket boundaries for the four key metrics; wire the actual `.record()`/`.add()` calls into the recording call sites marked in Section 5.
- Decide and apply real span names/attributes for the events `OTelCallbackHandler` (Section 4) receives (e.g. what request/response data belongs on the `classify_intent` chain span vs. the `generate_response` chain span vs. the nested LLM-call span within it).
- Build Grafana dashboards in `observability/grafana/dashboards/` visualizing `/chat` latency percentiles, intent distribution, LLM call duration, and RAG retrieval rate.
- Get the pipeline showing real data end-to-end via `docker-compose up` and debug any gaps (missing spans, empty Prometheus targets, no Grafana data, missing trace/log correlation) collaboratively rather than solo.
- Evaluate whether LangSmith is worth adopting alongside or instead of the hand-rolled node spans.
- Scope and design actual CloudWatch log shipping as part of Step 9 (AWS Deployment), once an AWS account/log group exists to target — the structured JSON logging from Section 3 is the prep work for that.
