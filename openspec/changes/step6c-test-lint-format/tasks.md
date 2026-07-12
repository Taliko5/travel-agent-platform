## 1. Prerequisite check

- [x] 1.1 Confirm `harden-ci-pipeline`'s ESLint setup (task group 1) has landed in `frontend/package.json`; if not, add `eslint` + `eslint-config-next` first so `eslint-config-prettier` has something to layer onto — not landed, added `eslint`/`eslint-config-next` + `frontend/.eslintrc.json` directly

## 2. Frontend test runner

- [x] 2.1 Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom` as frontend devDependencies (also `@vitejs/plugin-react`, needed by `vitest.config.ts`)
- [x] 2.2 Add `frontend/vitest.config.ts` (jsdom environment, path aliases matching `tsconfig.json`)
- [x] 2.3 Replace the placeholder `"test"` script in `frontend/package.json` with `vitest run`
- [x] 2.4 Add `@vitest/coverage-v8` devDependency; configure `vitest.config.ts` with `coverage: { provider: 'v8', reporter: ['text', 'json'] }` (no thresholds set) — verified via `vitest run --coverage`
- [x] 2.5 Add `frontend/src/test-utils.tsx` exporting `renderWithProviders` — wraps RTL's `render` with the existing `Providers` component (`frontend/src/app/providers.tsx`), re-exports RTL's other utilities (`screen`, `fireEvent`, etc.) for a single import point

## 3. Frontend component tests

All tests below use `renderWithProviders` from `frontend/src/test-utils.tsx` (task 2.5) instead of RTL's default `render`, since every component runs inside `ChakraProvider` with the custom "unicorn" theme in production. 21 tests total, all passing.

- [x] 3.1 `ChatInput.test.tsx` — controlled input updates, submit triggers callback, disabled state while loading
- [x] 3.2 `MessageBubble.test.tsx` — markdown rendering (bold/headings/lists via `react-markdown`), conditional intent label
- [x] 3.3 `MessageList.test.tsx` — renders a list of messages as `MessageBubble`s (note: the "shows ThinkingIndicator when loading" behavior actually lives in `ChatInterface.tsx`, not `MessageList.tsx` — moved that assertion into 3.5; `MessageList` itself doesn't import Chakra, but its rendered child `MessageBubble` does, so it still needs `renderWithProviders`)
- [x] 3.4 `ThinkingIndicator.test.tsx` — renders the bounce/thinking UI
- [x] 3.5 `ChatInterface.test.tsx` — mocks `fetch`, asserts `POST` request shape to the chat endpoint, mocked response renders, thinking indicator shows during the in-flight request and hides after, error state, input clears on submit
- [x] 3.6 `SparkleHeader.test.tsx` — smoke test only (renders without crashing); no deeper assertions since it's stateless/decorative

## 4. Frontend formatter

- [x] 4.1 Add `prettier` and `eslint-config-prettier` as frontend devDependencies
- [x] 4.2 Add `.prettierrc` (and `.prettierignore`) at `frontend/`
- [x] 4.3 Add `prettier` to the ESLint `extends` array (after `next/core-web-vitals`) so stylistic rules don't conflict
- [x] 4.4 Add `format` (`prettier --write .`) and `format:check` (`prettier --check .`) scripts to `frontend/package.json`

## 5. Backend test coverage

63 tests total (16 new), all passing.

- [x] 5.1 `backend/tests/test_graph_routing.py` — `route_by_intent` for weather / hotel / transportation+flight-keyword / transportation without flight-keyword / other intents
- [x] 5.2 `backend/tests/test_api_main.py` — `/health`, `/`, `/chat` via FastAPI `TestClient` with `api.main.graph` mocked (`AsyncMock`); assert response shape and status codes
- [x] 5.3 Extend `test_api_main.py` with CORS assertions: `Access-Control-Allow-Origin` present for `http://localhost:3000`, absent/mismatched for other origins
- [x] 5.4 `backend/tests/test_rag_retriever.py` — `retrieve_context` with `get_vectorstore` mocked; assert `k` passed through and results joined correctly

## 6. Backend formatter

- [x] 6.1 Run `ruff format backend/` locally once to establish a formatted baseline — 13 files reformatted
- [x] 6.2 No new dependency needed — `ruff format` ships with the existing `ruff` install (found and fixed a separate gap: `pytest`, `pytest-asyncio`, and `ruff` were installed locally but missing from `backend/requirements.txt`, so CI's `pip install` step wouldn't have provided them — added all three, pinned to installed versions)

## 7. Fix existing violations

- [x] 7.1 Run `ruff format backend/` and `ruff check backend/ --fix`, resolve any remaining findings that require manual judgment — `ruff check` was already clean; format-only fixes needed
- [x] 7.2 Run `prettier --write` and `npm run lint` (frontend), resolve any remaining ESLint findings that require manual judgment — ESLint was already clean; 3 files needed Prettier formatting
- [x] 7.3 Confirm `pytest backend/tests/ -v` and `npm test` (frontend) both still pass after formatting changes — 63/63 backend, 21/21 frontend, frontend `next build` also verified clean

## 8. CI wiring

- [x] 8.1 Add `ruff format --check backend/` as a step in the `test` job (after `ruff check`) in `.github/workflows/ci.yml`
- [ ] 8.2 Add `npm run format:check` as a step in the `frontend` job (after lint, before/alongside test) in `.github/workflows/ci.yml` — **blocked**: no `frontend` job exists yet in `ci.yml`; that job is introduced by `harden-ci-pipeline`, not yet applied. Verified locally (`npm run format:check` passes) instead.
- [ ] 8.3 Confirm the `frontend` job's `npm test` step now runs the real Vitest suite (already updated in task 2.3 — verify in CI, not just locally) — **blocked**, same reason as 8.2. Verified locally (`npm test` passes, 21/21).
- [ ] 8.4 Confirm all CI jobs pass end-to-end on a PR — **deferred**: requires an actual push/PR to observe GitHub Actions; also transitively blocked on 8.2/8.3 for full coverage. Backend-side CI additions (8.1, 9.2) are ready to verify once pushed.

## 9. Coverage reporting (non-gating)

- [x] 9.1 Add `pytest-cov` to `backend/requirements.txt`
- [x] 9.2 Add a coverage step to the `test` job: folded into the existing "Run tests" step as `pytest --cov=backend --cov-report=term backend/tests/ -v` (avoids running the suite twice) — report-only, no `--cov-fail-under`
- [ ] 9.3 Add a coverage step to the `frontend` job: `vitest run --coverage` (uses the config from task 2.4) — **blocked**, same reason as 8.2. Verified locally: coverage report generates correctly (90%+ on components).
- [ ] 9.4 Confirm both coverage reports print in CI logs and neither step's exit code is affected by the coverage numbers themselves — backend confirmed locally with the exact CI command; frontend deferred with 9.3.

## 10. Docs sync

- [x] 10.1 Update `docs/plan.md`'s "Step 6c" entry (stubbed by `harden-ci-pipeline` as "Frontend unit tests") — retitled to "Step 6c: Testing, Linting & Formatting" reflecting the full scope landed here (frontend + backend tests, both formatters, non-gating coverage reporting, and the requirements.txt fix), appended under the existing Step 6 section
