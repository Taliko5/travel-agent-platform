## ADDED Requirements

### Requirement: Frontend unit test suite
The system SHALL provide an executable frontend unit test suite (Vitest + React Testing Library) covering `ChatInterface`, `MessageList`, `MessageBubble`, `ChatInput`, `ThinkingIndicator`, and `SparkleHeader` (smoke test only), runnable via `npm test`.

#### Scenario: Running the suite
- **WHEN** a developer or CI runs `npm test` in `frontend/`
- **THEN** the real test suite executes (not the placeholder script) and reports pass/fail per test

#### Scenario: ChatInterface sends a chat request
- **WHEN** a user submits a message through the chat UI in a test environment with `fetch` mocked
- **THEN** the test asserts a `POST` request is made to the chat endpoint with the message in the request body, and the mocked response is rendered

#### Scenario: MessageBubble renders markdown
- **WHEN** an assistant message containing Markdown syntax (e.g. `**bold**`, a heading) is rendered by `MessageBubble`
- **THEN** the test asserts the corresponding HTML elements (e.g. `<strong>`, heading tags) are present, not literal Markdown characters

#### Scenario: ChatInterface shows the thinking indicator while loading
- **WHEN** `ChatInterface` has an in-flight request (the `loading` state it manages directly, rendered alongside `MessageList` rather than inside it)
- **THEN** the test asserts `ThinkingIndicator` is present while loading and absent once the request resolves

### Requirement: Backend unit test coverage for routing, API, and retrieval
The system SHALL provide pytest coverage for `agent/graph.py`'s `route_by_intent`, `api/main.py`'s `/health`, `/`, and `/chat` endpoints, and `rag/retriever.py`'s `retrieve_context`, without requiring a `GOOGLE_API_KEY`.

#### Scenario: Routing by intent
- **WHEN** `route_by_intent` is called with a state whose `intent` is `"weather"`, `"hotel"`, `"transportation"` with flight keywords, `"transportation"` without flight keywords, or any other intent
- **THEN** it returns `"call_weather_tool"`, `"call_hotel_tool"`, `"call_flight_tool"`, `"retrieve_context"`, or `"retrieve_context"` respectively

#### Scenario: /chat endpoint returns the graph's result
- **WHEN** a `POST /chat` request is made with `api.main.graph` mocked to return a canned intent/response
- **THEN** the endpoint returns HTTP 200 with a JSON body matching `ChatResponse`'s shape, without invoking any real LLM call

#### Scenario: CORS allows the configured frontend origin
- **WHEN** a request to any endpoint includes `Origin: http://localhost:3000`
- **THEN** the response includes `Access-Control-Allow-Origin: http://localhost:3000`

#### Scenario: CORS rejects an unconfigured origin
- **WHEN** a request includes an `Origin` header not in the allowed list
- **THEN** the response does not include a matching `Access-Control-Allow-Origin` header for that origin

#### Scenario: retrieve_context queries the vector store
- **WHEN** `retrieve_context(query, k=2)` is called with `get_vectorstore` mocked to return documents
- **THEN** the mocked `similarity_search` is called with the given query and `k`, and the returned context joins document contents

### Requirement: Shared Chakra-aware test render helper
The system SHALL provide a `renderWithProviders` helper (`frontend/src/test-utils.tsx`) that wraps React Testing Library's `render` with the application's real `Providers` component, and every frontend component test SHALL use it instead of RTL's default `render`.

#### Scenario: Component relying on theme context renders correctly under test
- **WHEN** a component that uses Chakra UI (directly or via a child it renders) is mounted in a test using `renderWithProviders`
- **THEN** it renders with the application's actual "unicorn" theme (`frontend/src/theme/index.ts`) available, matching production context

#### Scenario: Bare RTL render is not used for these components
- **WHEN** a test file under `frontend/src/app/components/**/*.test.tsx` renders a component covered by this suite
- **THEN** it does so via `renderWithProviders`, not RTL's default `render`

### Requirement: Non-gating coverage reporting
The system SHALL report test coverage for both stacks (`vitest run --coverage` for frontend, `pytest --cov=backend` for backend) as part of CI, without failing a job based on coverage percentage.

#### Scenario: Coverage report generated on a normal run
- **WHEN** the `frontend` or `test` CI job runs
- **THEN** a coverage report is produced and visible in CI output, in addition to the existing test pass/fail results

#### Scenario: Low coverage does not fail CI
- **WHEN** coverage for either stack is low or drops between runs
- **THEN** the CI job's pass/fail outcome is unaffected — only test failures (not coverage numbers) can fail the job

### Requirement: Backend code formatting
The system SHALL enforce `ruff format --check` on `backend/` as part of CI, in addition to the existing `ruff check` lint step.

#### Scenario: Formatted code passes
- **WHEN** all files under `backend/` conform to `ruff format`'s output
- **THEN** the `ruff format --check backend/` step passes

#### Scenario: Unformatted code fails the check
- **WHEN** a file under `backend/` does not match `ruff format`'s output
- **THEN** the `ruff format --check backend/` step fails, without modifying the file (check-only, not auto-fix)

### Requirement: Frontend code formatting
The system SHALL provide a Prettier configuration for the frontend, enforced via a `format:check` script compatible with the project's ESLint configuration (no conflicting stylistic rules).

#### Scenario: Formatted code passes
- **WHEN** all files under `frontend/src/` conform to the committed Prettier configuration
- **THEN** `npm run format:check` passes

#### Scenario: Unformatted code fails the check
- **WHEN** a file under `frontend/src/` does not match the Prettier configuration's output
- **THEN** `npm run format:check` fails, without modifying the file
