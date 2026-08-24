## ADDED Requirements

### Requirement: Configurable Request Deadline
The system SHALL enforce a maximum wall-clock duration on the graph invocation underlying `POST /chat`, configurable via the `CHAT_REQUEST_TIMEOUT_SECONDS` environment variable, defaulting to `30` seconds when unset.

#### Scenario: Graph invocation completes within the deadline
- **WHEN** the graph invocation underlying a `/chat` request completes before `CHAT_REQUEST_TIMEOUT_SECONDS` elapses
- **THEN** the system SHALL return the normal response, unaffected by the deadline mechanism

#### Scenario: Graph invocation exceeds the deadline
- **WHEN** the graph invocation underlying a `/chat` request has not completed after `CHAT_REQUEST_TIMEOUT_SECONDS` seconds
- **THEN** the system SHALL cancel the in-flight graph invocation and SHALL NOT continue waiting on it

### Requirement: Timeout Response
When the request deadline is exceeded, the system SHALL respond with HTTP `504 Gateway Timeout` and a JSON body containing a `detail` field, instead of the normal `200` response shape.

#### Scenario: Client receives a 504 on timeout
- **WHEN** a `/chat` request's graph invocation exceeds `CHAT_REQUEST_TIMEOUT_SECONDS`
- **THEN** the HTTP response status SHALL be `504`
- **AND** the response body SHALL be JSON containing a `detail` field describing the timeout

### Requirement: Timeout Observability
A timed-out request SHALL be recorded as `status="error"` on the existing `chat_request_duration_seconds` histogram — no additional `status` label value SHALL be introduced for timeouts. The system SHALL additionally increment a dedicated, label-less `chat_request_timeout_total` counter, which SHALL be pre-seeded at `0` so it is visible on `/metrics` before any timeout has occurred.

#### Scenario: Timeout recorded on the existing latency histogram
- **WHEN** a `/chat` request times out
- **THEN** `chat_request_duration_seconds` SHALL record an observation with `status="error"`
- **AND** no `status` value other than `ok` or `error` SHALL be produced by this or any other `/chat` outcome

#### Scenario: Timeout counter increments
- **WHEN** a `/chat` request times out
- **THEN** `chat_request_timeout_total` SHALL increment by 1

#### Scenario: Timeout counter visible before any timeout has occurred
- **WHEN** the backend process starts and no `/chat` request has yet timed out
- **THEN** `chat_request_timeout_total` SHALL already be present on `/metrics`, at value `0`
