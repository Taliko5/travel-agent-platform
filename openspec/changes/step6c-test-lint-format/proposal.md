## Why

`harden-ci-pipeline` wires CI structure (frontend job runs lint → `npm test` → build) but explicitly defers the substance: no frontend test runner exists (no Jest/Vitest, no test files for any of the 6 components), the frontend `test` step is a placeholder script, no code formatter exists for either stack (only `ruff check` for lint on the backend, nothing on the frontend), and three backend modules (`agent/graph.py` routing, `api/main.py` endpoints, `rag/retriever.py`) have zero test coverage despite being the actual request-handling path. `harden-ci-pipeline`'s tasks stub a "Step 6c: Frontend unit tests" entry in `docs/plan.md` naming this exact gap. This change does that work — and, per explicit request, bundles in backend test coverage and a formatter for both stacks under the same "6c" label, since they're the same category of gap (code quality tooling that was never set up) and are cheaper to land together than sequenced separately.

## What Changes

- Add a frontend test runner (Vitest + React Testing Library + jsdom — see `design.md` for the choice over Jest) and write unit tests for `ChatInterface.tsx`, `MessageList.tsx`, `MessageBubble.tsx`, `ChatInput.tsx`, and `ThinkingIndicator.tsx`. `SparkleHeader.tsx` gets a minimal smoke test only (purely decorative, no logic/state per its own doc comment).
- Replace `frontend/package.json`'s placeholder `"test"` script (added by `harden-ci-pipeline`) with a real `vitest run` invocation — no CI workflow change needed, per that change's design.
- Add Prettier to the frontend (`eslint-config-prettier` to avoid ESLint/Prettier rule conflicts), with a committed `.prettierrc` and `format` / `format:check` scripts.
- Add three backend test files: `test_graph_routing.py` (`route_by_intent` — weather/hotel/flight-keyword transportation/non-flight transportation branches), `test_api_main.py` (`/health`, `/`, `/chat` via FastAPI `TestClient`, with `api.main.graph` mocked so no real LLM call happens; also asserts the CORS header behavior added in Step 6), and `test_rag_retriever.py` (`retrieve_context` with `get_vectorstore` mocked, verifying `k` is passed through and results are joined correctly).
- Enable `ruff format --check backend/` as the backend formatter (ruff already installed — no new dependency, just a new check).
- **Fix existing violations**: run the new formatter/linter over current source and resolve whatever it flags, so CI starts green rather than immediately red on unrelated pre-existing code.
- Extend `.github/workflows/ci.yml`'s `frontend` and `test` jobs (introduced by `harden-ci-pipeline`) with format-check steps, and point the frontend job's real test invocation at the new suite.
- Update `docs/plan.md`'s "Step 6c" entry (stubbed by `harden-ci-pipeline` as "Frontend unit tests") to reflect the actual, broader scope landed here — retitled to cover testing, linting, and formatting for both stacks — and mark it Done.

## Capabilities

### New Capabilities
- `code-quality`: automated test suites (frontend + backend) and code formatters (frontend + backend) that give the CI pipeline something real to enforce, beyond the lint/build checks `harden-ci-pipeline` already wires up.

### Modified Capabilities
_None._ `harden-ci-pipeline`'s `ci-pipeline` capability is not modified via a delta here — it hasn't been archived into `openspec/specs/` yet (still an in-flight change), so there's no base spec to target a MODIFIED delta against. This change's `ci.yml` edits (format-check steps, swapping the placeholder test script) are implementation detail that extends what `ci-pipeline` already specifies, not a change to its requirements. See `design.md`'s Open Questions for how the two changes should be sequenced/reconciled at archive time.

## Impact

- `frontend/package.json`, `frontend/vitest.config.ts` (or equivalent), new `frontend/src/**/*.test.tsx` files, `.prettierrc`, `frontend/.eslintrc.json` extended with `prettier` — new devDependencies, config, and test files.
- `backend/tests/test_graph_routing.py`, `backend/tests/test_api_main.py`, `backend/tests/test_rag_retriever.py` — new test files.
- `.github/workflows/ci.yml` — extends (not restructures) the jobs `harden-ci-pipeline` introduces: adds format-check steps, replaces the placeholder frontend test command.
- `docs/plan.md` — Step 6c entry filled in and marked Done.
- Sequencing dependency on `harden-ci-pipeline`: this change assumes ESLint (added there) and the job skeleton already exist. If implemented before `harden-ci-pipeline` lands, tasks below note where to check/add the ESLint prerequisite instead of assuming it.
