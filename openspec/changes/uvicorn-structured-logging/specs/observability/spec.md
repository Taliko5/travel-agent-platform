## MODIFIED Requirements

### Requirement: Structured Logging with Trace Correlation
The system SHALL emit backend logs in structured (JSON) format, with the active OpenTelemetry `trace_id` and `span_id` attached to each log record when a span is active, so a log line can be correlated back to the trace/request that produced it. This applies to every log line the backend process emits to its own stdout, including `uvicorn.access` and `uvicorn.error` — a line is not exempt from this requirement by virtue of which logger produced it.

#### Scenario: A log is emitted during an active span
- **WHEN** the backend logs a message while handling a request that has an active span (e.g. inside a `/chat` request)
- **THEN** the emitted JSON log record SHALL include the current `trace_id` and `span_id`

#### Scenario: A log is emitted outside any active span
- **WHEN** the backend logs a message with no active span (e.g. during application startup)
- **THEN** the emitted JSON log record SHALL still be valid structured JSON, with `trace_id`/`span_id` fields present but empty or null rather than causing an error

#### Scenario: Uvicorn's access line for a completed request
- **WHEN** uvicorn logs its access line for a request, after the ASGI application has already returned control to it
- **THEN** that line SHALL be valid structured JSON, in the same format as the rest of the backend's logs
- **AND** it SHALL carry `trace_id`/`span_id` fields present but null, consistent with the request's span having already ended — not a defect to engineer around
