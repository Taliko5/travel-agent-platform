## MODIFIED Requirements

### Requirement: Placeholder Metric Instruments for Key Metrics
The system SHALL record `/chat` request latency and classified-intent counts with explicitly bounded label sets, and SHALL declare — without yet recording — instruments for LLM call duration and RAG retrieval rate. This supersedes the scaffold's requirement that all four instruments be declared but unrecorded.

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

#### Scenario: An instrument with no recording call site
- **WHEN** the backend runs with `llm_call_duration_seconds` and `rag_retrieval_total` declared but having no recording call sites
- **THEN** both SHALL remain importable from the module that declares them
- **AND** `/metrics` SHALL still return successfully

### Requirement: Automated Tests for Scaffolded Instrumentation
The system SHALL include a test asserting that seeded counters appear on `/metrics` and that unseeded histograms do not. This supersedes the scaffold's requirement that the test assert all four declared instrument names appear.

#### Scenario: Metrics endpoint test
- **WHEN** the test suite runs
- **THEN** a test SHALL assert that the seeded counters are present in the `/metrics` body
- **AND** SHALL assert that `llm_call_duration_seconds` is absent — the one instrument with no recording call site anywhere, so no test ordering can populate it
- **AND** SHALL NOT assert the absence of `chat_request_duration_seconds`, because `/metrics` is process-global state and earlier tests in the same session record into it

## ADDED Requirements

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
