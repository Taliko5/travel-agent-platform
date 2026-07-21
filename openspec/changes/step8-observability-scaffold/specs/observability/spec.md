## ADDED Requirements

### Requirement: OpenTelemetry SDK Wiring in the Backend
The system SHALL initialize an OpenTelemetry `TracerProvider` and `MeterProvider` when the FastAPI app starts, tagged with a `Resource` identifying `service.name`, `service.version`, and `deployment.environment`, and SHALL auto-instrument inbound HTTP requests via `FastAPIInstrumentor`, without requiring any environment configuration beyond what's already needed to run `uvicorn api.main:app`.

#### Scenario: App starts without OTel-specific environment variables set
- **WHEN** the backend starts with only the existing required environment (e.g. `GOOGLE_API_KEY`) present
- **THEN** the app SHALL start successfully with a configured `TracerProvider`/`MeterProvider`
- **AND** the associated `Resource` SHALL include `service.name` and `service.version`, with `deployment.environment` defaulting to `local` when no override is set

#### Scenario: A request to any HTTP route produces a span
- **WHEN** a client sends a request to any FastAPI route (e.g. `/health`, `/chat`)
- **THEN** the system SHALL emit a span for that HTTP request via `FastAPIInstrumentor`, attributed to the configured `Resource`

### Requirement: Configurable Trace Exporter
The system SHALL export spans to an OTLP endpoint when `OTEL_EXPORTER_OTLP_ENDPOINT` is set in the environment, and SHALL fall back to a console exporter when it is unset, without requiring a code change to switch between them.

#### Scenario: No OTLP endpoint configured
- **WHEN** the backend starts with `OTEL_EXPORTER_OTLP_ENDPOINT` unset
- **THEN** spans SHALL be exported via a console exporter

#### Scenario: OTLP endpoint configured
- **WHEN** the backend starts with `OTEL_EXPORTER_OTLP_ENDPOINT` set to a reachable OTLP collector address
- **THEN** spans SHALL be exported to that endpoint instead of the console

### Requirement: Prometheus-Scrapable Metrics Endpoint
The system SHALL expose a `/metrics` HTTP endpoint on the backend that returns metrics in Prometheus text exposition format.

#### Scenario: Prometheus scrapes the backend
- **WHEN** an HTTP GET request is made to `/metrics` on the backend
- **THEN** the system SHALL return a `200` response with `Content-Type` compatible with Prometheus text exposition format

### Requirement: LangGraph/LangChain Span Instrumentation via Callback Handler
The system SHALL provide a `BaseCallbackHandler` (`OTelCallbackHandler`) that translates LangChain/LangGraph node, LLM, and tool callback events into spans, registered once at graph-invocation time, without requiring modifications to `backend/agent/graph.py` or `backend/agent/nodes.py`, and without altering the `AgentState` produced by a run or the propagation of exceptions raised during it.

#### Scenario: A node completes successfully
- **WHEN** a graph run invokes a node (e.g. `classify_intent`) with `OTelCallbackHandler` registered via invocation `config`, and the node returns normally
- **THEN** the system SHALL emit a span covering that node's execution, opened in `on_chain_start` and closed in `on_chain_end`
- **AND** the returned `AgentState` SHALL be identical to what the same run would produce without the handler registered

#### Scenario: A node raises an exception
- **WHEN** a node raises an exception during execution while `OTelCallbackHandler` is registered
- **THEN** the system SHALL end the span for that node via `on_chain_error`
- **AND** SHALL NOT interfere with the original exception propagating unchanged, so existing routing/error-handling behavior is unaffected

#### Scenario: An LLM call within a node produces a nested span
- **WHEN** a node invokes the chat model as a LangChain Runnable (e.g. inside `classify_intent` or `generate_response`)
- **THEN** the system SHALL emit a span for that LLM call, opened in `on_llm_start` and closed in `on_llm_end` (or `on_llm_error` on failure), nested under the enclosing node's span

### Requirement: Placeholder Metric Instruments for Key Metrics
The system SHALL declare named metric instruments (counters/histograms) corresponding to `/chat` request latency, classified intent distribution, LLM call duration, and RAG retrieval rate, as a starting point for recording calls to be added later, without prescribing final label sets or bucket boundaries.

#### Scenario: Instruments are declared but not yet recorded
- **WHEN** the backend starts with the scaffolded instrumentation in place, before any recording calls are added
- **THEN** the four named instruments SHALL exist and be importable/referenceable from the module that declares them
- **AND** `/metrics` SHALL still return successfully (an instrument with no recorded data points is not an error)

### Requirement: Structured Logging with Trace Correlation
The system SHALL emit backend logs in structured (JSON) format, with the active OpenTelemetry `trace_id` and `span_id` attached to each log record when a span is active, so a log line can be correlated back to the trace/request that produced it.

#### Scenario: A log is emitted during an active span
- **WHEN** the backend logs a message while handling a request that has an active span (e.g. inside a `/chat` request)
- **THEN** the emitted JSON log record SHALL include the current `trace_id` and `span_id`

#### Scenario: A log is emitted outside any active span
- **WHEN** the backend logs a message with no active span (e.g. during application startup)
- **THEN** the emitted JSON log record SHALL still be valid structured JSON, with `trace_id`/`span_id` fields present but empty or null rather than causing an error

### Requirement: Local Prometheus and Grafana Services with Persistent Storage
The system SHALL provide `prometheus` and `grafana` services in `docker-compose.yaml` that can reach the backend's `/metrics` endpoint on the compose network, with Grafana pre-configured to query the Prometheus service as a datasource, and with each service's data persisted in a named Docker volume so it survives a container restart.

#### Scenario: Full stack starts via docker-compose
- **WHEN** a user runs `docker-compose up --build`
- **THEN** the `prometheus` and `grafana` services SHALL start alongside `backend` and `frontend`
- **AND** the `backend` service SHALL NOT depend on `prometheus`/`grafana` being healthy to start

#### Scenario: Prometheus scrapes the backend target
- **WHEN** the `prometheus` service is running with its provisioned scrape config
- **THEN** Prometheus SHALL list the backend's `/metrics` endpoint as a scrape target

#### Scenario: Grafana has a working Prometheus datasource
- **WHEN** a user opens the Grafana UI
- **THEN** a Prometheus datasource pointing at the compose `prometheus` service SHALL already be configured, without manual datasource setup

#### Scenario: Restarting the stack preserves prior data
- **WHEN** a user runs `docker-compose restart prometheus grafana` (not `down -v`) after metrics have been scraped
- **THEN** previously scraped Prometheus data and Grafana configuration SHALL still be present after the restart

### Requirement: Automated Tests for Scaffolded Instrumentation
The system SHALL include automated tests that directly exercise the new instrumentation code — the `/metrics` endpoint and `OTelCallbackHandler` — separately from confirming pre-existing tests still pass.

#### Scenario: Metrics endpoint test
- **WHEN** the test suite runs
- **THEN** a test SHALL assert that `GET /metrics` returns `200` and that the response body contains the names of the four declared placeholder instruments

#### Scenario: Callback handler span-lifecycle test
- **WHEN** the test suite runs
- **THEN** a test SHALL assert that invoking `OTelCallbackHandler`'s success callbacks (`on_chain_start`/`on_chain_end`) ends the span it opened, and that invoking its error callbacks (`on_chain_error`, and equivalently `on_llm_error`/`on_tool_error`) also ends the span, without the handler itself raising or swallowing anything

### Requirement: Observability Documentation
The system SHALL include `docs/step8.md` describing what is instrumented, why each piece of the stack exists, and which parts are scaffolded versus left for hands-on user implementation, including a note on LangSmith as a considered-but-not-adopted alternative for LangGraph-native tracing.

#### Scenario: A reader wants to know what's already done vs. left for them
- **WHEN** a user reads `docs/step8.md`
- **THEN** the document SHALL clearly distinguish scaffolded components (compose services, SDK wiring, span hooks, placeholder instruments, structured logging) from components the user is expected to implement (metric definitions, span naming/attributes, dashboards, end-to-end verification)

#### Scenario: A reader wants to know about deferred work
- **WHEN** a user reads `docs/step8.md`
- **THEN** the document SHALL note that CloudWatch log *shipping* is deferred to Step 9, and that the structured JSON logging added in this change is the prep work for that step
