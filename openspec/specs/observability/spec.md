# observability

## Purpose

Instrumentation for the FastAPI backend and LangGraph agent (OpenTelemetry, Prometheus, Grafana) that makes a `/chat` request's latency, classified intent, and LLM and RAG calls visible as metrics, spans, and trace-correlated JSON logs.

## Requirements

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
The system SHALL provide a `BaseCallbackHandler` (`OTelCallbackHandler`) that translates LangChain/LangGraph node, LLM, and tool callback events into spans, registered once at graph-invocation time, without requiring modifications to `backend/agent/graph.py` or `backend/agent/nodes.py`, and without altering the `AgentState` produced by a run or the propagation of exceptions raised during it. Span names SHALL identify an operation type, never a specific occurrence, and span attributes SHALL be limited to values a query would plausibly filter or group by — never the full text of a request's user input, a model's output, or any other free-text `AgentState` payload field. This supersedes the scaffold's requirement only by specifying what its span names and attributes must satisfy; the scaffold left both undecided.

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

#### Scenario: A span name identifies an operation type, not an occurrence
- **WHEN** any span is opened for a node, an LLM call, or a tool call
- **THEN** its name SHALL be the same for every invocation of that node, that LLM-call type, or that tool
- **AND** SHALL NOT be built from user input, model output, or any other per-request value

#### Scenario: Node spans carry the request's classified intent, once known
- **WHEN** a node span is opened for `classify_intent` itself, or for any node that executes after `classify_intent` has resolved an intent
- **THEN** that span SHALL carry an `intent` attribute once the intent is known — set from the node's own output for `classify_intent`, and from `AgentState` for every node afterward
- **AND** its value SHALL belong to the same bounded set `chat_request_duration_seconds`'s `intent` label uses, and SHALL agree with the value recorded on that metric for the same request
- **AND** a span opened before an intent is known SHALL carry no `intent` attribute, rather than a placeholder value outside that set

#### Scenario: The chat-model span uses OpenTelemetry's GenAI attribute names
- **WHEN** a span is opened for a chat-model call (`on_llm_start`/`on_chat_model_start`)
- **THEN** it SHALL carry `gen_ai.provider.name`, `gen_ai.request.model`, and `gen_ai.operation.name`, using OpenTelemetry's GenAI semantic-convention attribute keys rather than invented ones
- **AND** SHALL NOT carry the prompt or the completion text

#### Scenario: No span carries free-text request or response content
- **WHEN** any span opened by `OTelCallbackHandler` — node, chat-model, or tool — is closed
- **THEN** none of its attributes SHALL contain the request's user input, the model's output, or any other free-text `AgentState` payload field (e.g. retrieved context, a tool's raw response)

### Requirement: Structured Logging with Trace Correlation
The system SHALL emit backend logs in structured (JSON) format, with the active OpenTelemetry `trace_id` and `span_id` attached to each log record when a span is active, so a log line can be correlated back to the trace/request that produced it. This applies to every log line the backend process emits to its own stdout, including `uvicorn.access` and `uvicorn.error` — a line is not exempt from this requirement by virtue of which logger produced it.

#### Scenario: A log is emitted during an active span
- **WHEN** the backend logs a message while handling a request that has an active span (e.g. inside a `/chat` request)
- **THEN** the emitted JSON log record SHALL include the current `trace_id` and `span_id`

#### Scenario: A log is emitted outside any active span
- **WHEN** the backend logs a message with no active span (e.g. during application startup)
- **THEN** the emitted JSON log record SHALL still be valid structured JSON, with `trace_id`/`span_id` fields present but empty or null rather than causing an error

#### Scenario: Uvicorn's access line for a traced request
- **WHEN** uvicorn logs its access line for a request on a route that is instrumented
- **THEN** that line SHALL be valid structured JSON, in the same format as the rest of the backend's logs
- **AND** it SHALL carry the same `trace_id` and `span_id` as the other log lines that request produced

#### Scenario: Uvicorn's access line for a route excluded from tracing
- **WHEN** uvicorn logs its access line for a request on a route excluded from HTTP instrumentation, for which no span is ever created
- **THEN** that line SHALL be valid structured JSON, in the same format as the rest of the backend's logs
- **AND** it SHALL carry `trace_id`/`span_id` fields present but null — the same outcome the scaffold's requirement already prescribes for a line emitted with no span active, and not a defect to engineer around

### Requirement: Local Prometheus and Grafana Services with Persistent Storage
The system SHALL provide `prometheus` and `grafana` services in `docker-compose.yaml` that can reach the backend's `/metrics` endpoint on the compose network, with Grafana pre-configured to query the Prometheus service as a datasource, with each service's data persisted in a named Docker volume so it survives a container restart, and with Prometheus' retention explicitly configured in the repository rather than left to whatever the image's default happens to be.

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

#### Scenario: Prometheus' retention is explicit and bounded
- **WHEN** the `prometheus` service starts with this repository's configuration
- **THEN** its effective `storage.tsdb.retention.time` and `storage.tsdb.retention.size` SHALL be values stated in a version-controlled file, not the image's undocumented default
- **AND** both values SHALL be finite — neither left unset in a way that makes either dimension unbounded

### Requirement: Automated Tests for Scaffolded Instrumentation
The system SHALL include a test asserting that seeded counters appear on `/metrics` and that unseeded histograms do not. This supersedes the scaffold's requirement that the test assert all four declared instrument names appear.

#### Scenario: Metrics endpoint test
- **WHEN** the test suite runs
- **THEN** a test SHALL assert that the seeded counters are present in the `/metrics` body
- **AND** SHALL assert that `llm_call_duration_seconds` is absent — this repository's `/chat` endpoint tests mock `api.main.graph` entirely, so no test ever invokes a real chat-model call through `OTelCallbackHandler`, regardless of that instrument having a recording call site
- **AND** SHALL NOT assert the absence of `chat_request_duration_seconds`, because `/metrics` is process-global state and earlier tests in the same session record into it

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

### Requirement: Recorded Metric Instruments for Key Metrics
The system SHALL record all four key metrics with explicitly bounded label sets: `/chat` request latency, classified-intent counts, individual LLM call duration, and RAG context retrieval count. This supersedes the scaffold's requirement that all four instruments be declared but unrecorded.

#### Scenario: A `/chat` request completes successfully
- **WHEN** a `POST /chat` request completes without raising
- **THEN** the system SHALL record one observation on `chat_request_duration_seconds` carrying an `intent` label and a `status` label
- **AND** `status` SHALL be `ok`
- **AND** `intent` SHALL be the intent the classifier resolved

#### Scenario: A `/chat` request fails
- **WHEN** a `POST /chat` request raises before returning a response
- **THEN** the system SHALL still record one observation on `chat_request_duration_seconds`
- **AND** `status` SHALL be `error`
- **AND** `intent` SHALL be the intent the classifier resolved if the graph run had already produced one, and `unknown` otherwise

#### Scenario: No third status value is ever produced
- **WHEN** a `POST /chat` request completes by any path whatsoever, including cancellation or timeout
- **THEN** the recorded `status` label SHALL be either `ok` or `error`, and SHALL NOT take any other value

#### Scenario: An LLM call completes
- **WHEN** a chat-model call made via `get_model().invoke(...)` completes, successfully or not
- **THEN** the system SHALL record one observation on `llm_call_duration_seconds` carrying a `node` label and a `status` label
- **AND** `node` SHALL be the name of the node whose span the call happened inside, or `unknown` where that name is no longer recoverable
- **AND** `node` SHALL always be present, never omitted — a series identified by a missing label is not a permitted outcome
- **AND** `status` SHALL be `ok` on success and `error` on failure

#### Scenario: No third status value is ever produced on an LLM call
- **WHEN** a chat-model call completes by any path whatsoever
- **THEN** the recorded `status` label on `llm_call_duration_seconds` SHALL be either `ok` or `error`, and SHALL NOT take any other value

#### Scenario: RAG context is retrieved
- **WHEN** the `retrieve_context` node runs
- **THEN** the system SHALL record one observation on `rag_retrieval_total` carrying an `intent` label
- **AND** `intent` SHALL be the intent the classifier resolved for that request
- **AND** the observation SHALL be recorded regardless of whether the retrieval itself succeeds

### Requirement: Metric Recording Is Additive
The system SHALL record metrics as an addition to existing behaviour only. No recording site SHALL alter the `AgentState` a run produces, the response a `POST /chat` request returns, or the propagation of an exception raised while handling it.

#### Scenario: A request that succeeds
- **WHEN** a `POST /chat` request is handled
- **THEN** every metric recording call site SHALL only read state the request has already established
- **AND** SHALL NOT write to the `AgentState` or alter the response returned to the caller

#### Scenario: A request raises
- **WHEN** a `POST /chat` request raises while being handled, and its outcome is recorded on `chat_request_duration_seconds`
- **THEN** the original exception SHALL propagate unchanged
- **AND** SHALL NOT be suppressed or replaced by anything the recording raises

### Requirement: Counter Seeding
The system SHALL seed every counter instrument at zero from a hook invoked after the `MeterProvider` is installed, and SHALL NOT seed histogram instruments.

#### Scenario: Backend has started and no request has been made
- **WHEN** the backend has started and no `POST /chat` request has been handled
- **THEN** `/metrics` SHALL expose each counter at 0
- **AND** `intent_classification_total` SHALL be exposed for every valid intent crossed with every value of its `fallback` label
- **AND** `rag_retrieval_total` SHALL be exposed for every valid intent
- **AND** none of the histogram instruments this system declares SHALL be exposed

#### Scenario: Seeding is attempted before the provider is installed
- **WHEN** a measurement is recorded on an instrument before the `MeterProvider` is installed
- **THEN** the system SHALL NOT depend on that measurement being exported, and the seeding hook SHALL therefore run after provider installation rather than at import time

#### Scenario: A new intent is added to the classifier
- **WHEN** a value is added to the classifier's set of valid intents
- **THEN** the seeded label combinations SHALL include it without a second, separate edit

### Requirement: Prometheus Scrapes the Backend Successfully
The system SHALL be scrapable by the bundled Prometheus at the path configured in `observability/prometheus.yml`, regardless of any redirection the backend's metrics mount introduces.

#### Scenario: Prometheus scrapes the configured path
- **WHEN** Prometheus scrapes the backend at its configured `metrics_path`
- **THEN** the scrape SHALL succeed
- **AND** the `up` series for that target SHALL be 1
- **AND** for as long as both Prometheus and that target are running, that series SHALL be continuous, with no sample absent from it

#### Scenario: The metrics path is requested without a trailing slash
- **WHEN** an HTTP GET is made to the metrics path without a trailing slash
- **THEN** the system SHALL either return the metrics directly or redirect to the canonical path
- **AND** a client that follows redirects SHALL obtain the metrics

### Requirement: Provisioned Grafana Dashboard
The system SHALL provision a Grafana dashboard from a version-controlled JSON file, with no manual import step.

#### Scenario: Grafana starts with the repository's provisioning configuration
- **WHEN** the `grafana` service starts with the repository's provisioning configuration mounted
- **THEN** Grafana SHALL load the dashboard from its file provider
- **AND** querying that dashboard through Grafana's API SHALL report it as provisioned, naming the source file

#### Scenario: Panel queries are evaluated against recorded data
- **WHEN** the dashboard's panel queries are evaluated while traffic from the load generator still falls within each query's own lookback window
- **THEN** every query-backed panel SHALL return a non-empty result

#### Scenario: A ratio panel is evaluated before its numerator has ever occurred
- **WHEN** a panel expressing a ratio is evaluated on a stack where no series has ever matched the numerator's label selector, so the numerator is absent rather than present at zero
- **THEN** the panel SHALL render zero rather than "No data"

### Requirement: Trace and Log Correlation for a Single Request
The system SHALL make the log lines emitted through the application's configured logging handler during a request's active span identifiable as belonging to that request. This does not extend to a line emitted by a logger that bypasses that handler, nor to one emitted after the request's span has ended, both of which are the scaffold's `Structured Logging with Trace Correlation` requirement to satisfy or not.

#### Scenario: A single request's log lines
- **WHEN** one `POST /chat` request is handled
- **THEN** each log line emitted through the application's configured logging handler while the request's span is active SHALL carry a non-null `trace_id`, whichever logger produced it
- **AND** all of those log lines SHALL share the same `trace_id`
- **AND** the completion line SHALL additionally carry the request's resolved intent, its status, and its duration

### Requirement: Self-Observation Excluded from Tracing
The system SHALL NOT emit HTTP spans for its own health and metrics endpoints, so that an idle stack produces no trace traffic.

#### Scenario: The stack idles with no user traffic
- **WHEN** the stack runs with no `POST /chat` traffic, while the compose healthcheck and Prometheus continue polling on their timers
- **THEN** the system SHALL emit no HTTP spans for the health or metrics paths

### Requirement: Reproducible Load Generation
The system SHALL include a committed script that generates enough `/chat` traffic for rate-based queries to be meaningful, at a default rate the Gemini free tier tolerates.

#### Scenario: The script runs at its defaults
- **WHEN** the load generator runs with no arguments
- **THEN** it SHALL exercise every routing branch of the agent
- **AND** SHALL NOT exceed the request rate the free tier permits

#### Scenario: A run is interrupted
- **WHEN** a run is terminated before it completes, with its output piped to a file
- **THEN** the progress already emitted SHALL be present in that file

#### Scenario: A run completes
- **WHEN** a run finishes
- **THEN** it SHALL report per-intent counts, HTTP status counts, minimum, mean and maximum observed latency, and total wall-clock time

