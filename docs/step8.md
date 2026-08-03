# Step 8: Observability (OpenTelemetry / Prometheus / Grafana)

## Goal

Instrument the backend so `/chat` latency, intent distribution, LLM call duration, and RAG retrieval rate can actually be observed, instead of relying on unstructured stdout. This is a scaffold: Claude Code wired the plumbing (SDK setup, compose services, placeholder instruments); defining real metrics, span names/attributes, and dashboards is your hands-on work — see "Scaffolded vs. Yours" below.

## What's Instrumented

**OTel SDK wiring (`backend/api/main.py`)** — a `TracerProvider` and `MeterProvider` are constructed at module load, tagged with a `Resource`: `service.name=travel-agent-backend`, `service.version=0.1.0` (reused from the FastAPI `app`), and `deployment.environment` (env var `DEPLOYMENT_ENVIRONMENT`, default `local`). Without these, every span/metric would be anonymous once a second service or environment exists.

**FastAPI HTTP spans** — `FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")` auto-instruments inbound HTTP requests, attributed to the same `Resource`. `/health` and `/metrics` are excluded: the docker-compose healthcheck (every 30s) and the Prometheus scrape (every 15s) would otherwise generate spans forever, even with zero user traffic.

**`/metrics` endpoint** — `opentelemetry.exporter.prometheus.PrometheusMetricReader` is wired into the `MeterProvider`, and `prometheus_client.make_asgi_app()` is mounted at `/metrics`, so Prometheus has something to scrape in text exposition format.

**LangGraph/LangChain span instrumentation via callback handler** — `backend/observability/callback_handler.py` defines `OTelCallbackHandler(BaseCallbackHandler)`. It's registered *once*, where the graph is invoked (`config={"callbacks": [otel_callback_handler]}` on `graph.ainvoke(...)` in `backend/api/main.py`) — not as a decorator on each node function, and without any changes to `backend/agent/graph.py` or `backend/agent/nodes.py`. LangChain's callback system fires `on_chain_start`/`on_chain_end` (or `on_chain_error`) for each LangGraph node, and `on_llm_start`/`on_llm_end`/`on_llm_error` for LLM calls made as a LangChain Runnable — the handler opens a span on `*_start` and closes it on the matching `*_end`/`*_error`, nesting child spans under their `parent_run_id`.

We verified this in a live `docker-compose up` smoke test (a real `/chat` weather request): the console exporter showed `ChatGoogleGenerativeAI` spans nested directly under `call_weather_tool` and `generate_response` node spans, which were themselves nested under a `LangGraph` span, under the FastAPI `POST /chat` span. Callback `config` propagation reached the nested `get_model().invoke(prompt)` call automatically — no `RunnableConfig` forwarding needed in `nodes.py`.

**Structured logging with trace correlation (`backend/observability/logging.py`)** — the stdlib root logger is configured with a JSON formatter (`python-json-logger`) and a `logging.Filter` that reads `trace.get_current_span().get_span_context()` and attaches `trace_id`/`span_id` to every log record (`None` when no span is active, e.g. at startup). This means a log line from inside a `/chat` request can be grepped by the same `trace_id` shown in the matching span — and since CloudWatch ingestion is line-oriented JSON either way, this is also the prep work for Step 9's log shipping.

**Placeholder metric instruments (`backend/observability/metrics.py`)** — four named instruments for the metrics named in `docs/plan.md`: `chat_request_duration_seconds` (histogram), `intent_classification_total` (counter), `llm_call_duration_seconds` (histogram), `rag_retrieval_total` (counter). Both histograms are given provisional `explicit_bucket_boundaries_advisory` values tuned for second-scale latencies (the OTel SDK's default boundaries assume milliseconds, which makes real `/chat`/LLM latencies uncomputable for percentiles) — these boundaries are a starting point, not a final decision. Only the two counters are seeded with a zero-value `.add(0)` call so they show up on `/metrics` immediately (OTel's Prometheus reader only exports an instrument once it has at least one data point); the histograms are deliberately left unseeded, since a fake `.record(0)` would inject a permanent false "0 seconds" observation that skews `histogram_quantile()` and average-latency calculations. That seed call is *not* the real recording logic; see the `# TODO (user)` comment on each instrument for where the actual `.record()`/`.add()` call belongs.

**Prometheus + Grafana (`docker-compose.yaml`, `observability/`)** — `prometheus` and `grafana` services scrape/visualize the backend. Prometheus is configured via `observability/prometheus.yml` to scrape `backend:8000/metrics` on the compose network. Grafana auto-provisions a Prometheus datasource (`observability/grafana/provisioning/datasources/prometheus.yml`) and a dashboard-provisioning path (`observability/grafana/provisioning/dashboards/default.yml` → `observability/grafana/dashboards/`, currently empty except a placeholder `README.md`). Both services use named volumes (`prometheus_data`, `grafana_data`) so scrape history and dashboard state survive `docker-compose restart`.

## Running Locally

```bash
docker-compose up --build
```

This starts `backend`, `frontend`, `prometheus` (port `9090`), and `grafana` (port `3001`, default login `admin`/`admin`). Neither `backend` nor `frontend` depends on the observability services being healthy — `docker-compose up backend frontend` still works standalone.

- Backend metrics: `http://localhost:8000/metrics`
- Prometheus UI / targets page: `http://localhost:9090/targets`
- Grafana: `http://localhost:3001`
- Console span output: `docker-compose logs backend` (or your terminal if running `uvicorn` directly) — this is the only way to see traces today, see "Risks" below.

To reset all observability data (as opposed to a plain restart, which preserves it): `docker-compose down -v`.

## Scaffolded vs. Yours

**Scaffolded (this change):**
- Resource-attributed `TracerProvider`/`MeterProvider`, configurable trace exporter (`BatchSpanProcessor` either way — console or OTLP), `FastAPIInstrumentor` (excluding `/health`/`/metrics`), `/metrics` endpoint
- `OTelCallbackHandler` producing node- and LLM-call-level spans automatically, including chat models via `on_chat_model_start`, with a bounded span dict so abandoned spans (cancellation, disconnect, timeout) don't leak memory over the process lifetime
- Four placeholder metric instruments (declared, not recorded), with provisional second-scale histogram bucket boundaries already set
- Structured JSON logging with `trace_id`/`span_id` correlation
- `prometheus`/`grafana` compose services with persistent storage and a provisioned datasource
- Tests exercising `/metrics` and `OTelCallbackHandler` directly, asserting on actually-exported spans rather than internal state (`backend/tests/test_observability.py`)

**Yours to build:**
- Final metric names and label sets for the four key metrics — wire the actual `.record()`/`.add()` calls at the call sites marked with `# TODO (user)` in `backend/observability/metrics.py`. Histogram bucket boundaries have provisional starting values but remain yours to tune once real latency data is available
- Real span names/attributes for the events `OTelCallbackHandler` receives (currently marked `# TODO (user)` in `backend/observability/callback_handler.py`) — e.g. what belongs on the `classify_intent` span vs. `generate_response` vs. the nested LLM-call span
- Grafana dashboards in `observability/grafana/dashboards/` (drop-in JSON is auto-provisioned via `observability/grafana/provisioning/dashboards/default.yml`)
- Getting the pipeline showing real, meaningful data end-to-end and debugging any gaps
- Evaluating whether LangSmith is worth adopting alongside or instead of the hand-rolled spans (see below)
- CloudWatch log **shipping** — deferred to Step 9 (needs an AWS account/log group). The structured JSON logging added here is the prep work; shipping itself (log group, IAM role, `awslogs`/FireLens driver config) is not in scope now.

## LangSmith as an Alternative

`langsmith` is already installed as a transitive dependency via `langchain`. It's LangGraph-native — per-node and per-LLM-call trace breakdowns with minimal setup (`LANGCHAIN_TRACING_V2=true` + an API key), no hand-rolled callback handler required. It's also just a `BaseCallbackHandler`, so it can be registered in the same `callbacks` list alongside `OTelCallbackHandler` for a side-by-side comparison rather than an either/or choice. It wasn't adopted here because it's a separate SaaS product from the Prometheus/Grafana stack `docs/plan.md` names for this step — worth your own evaluation if you want richer LangGraph-specific trace views than the console exporter gives you.

## Trace Backend

By default, spans go to a `ConsoleSpanExporter` (visible via `docker-compose logs backend`), which is noisy and easy to miss in normal operation. It's wrapped in a `BatchSpanProcessor` (not `SimpleSpanProcessor`), so console writes happen on a background thread instead of blocking the request path on every span end. Setting `OTEL_EXPORTER_OTLP_ENDPOINT` in the environment switches to `OTLPSpanExporter` pointed at that endpoint — the one-variable path to a real trace backend (Jaeger, Tempo, Grafana Cloud, etc.) once you want trace visualization instead of console output. No code change needed either way.

## Risks / Notes

- No trace backend by default means spans are only visible via noisy console output until `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- The two placeholder counters (`intent_classification_total`, `rag_retrieval_total`) will show `0` on `/metrics` until you wire in real recording calls — that's intentional scaffolding, not a bug. The two histograms (`chat_request_duration_seconds`, `llm_call_duration_seconds`) intentionally do **not** appear on `/metrics` at all until real recording is added — seeding a histogram with a zero value would inject a permanent fake "0 seconds" observation and skew percentile/average calculations from the first scrape.
- `docker-compose down -v` removes the named Prometheus/Grafana volumes; a plain `restart` does not (verified during Step 8 implementation).
