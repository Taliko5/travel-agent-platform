## Context

Zero automated tests exist for the frontend (`frontend/src/app/components/*.tsx` — `ChatInterface`, `MessageList`, `MessageBubble`, `ChatInput`, `SparkleHeader`, `ThinkingIndicator`). `harden-ci-pipeline` wires a `frontend` CI job that runs `npm test`, but against a deliberate placeholder script — by design, so that landing this change requires no further CI YAML edits, only swapping the script body. On the backend, `pytest backend/tests/` only covers the three MCP tool servers (`test_step4_{flights,hotels,weather}.py`); `agent/graph.py`'s `route_by_intent`, `api/main.py`'s three endpoints (including the CORS middleware added mid-Step-6), and `rag/retriever.py`'s `retrieve_context`/`get_vectorstore` have no coverage. Neither stack has a formatter — backend has `ruff check` (lint only), frontend has nothing at all until `harden-ci-pipeline` adds ESLint (also lint only).

## Goals / Non-Goals

**Goals:**
- Real, executed test coverage for every frontend component and the three previously-untested backend modules.
- A formatter for each stack, wired into CI as a check (not auto-fixing in CI — see Decisions).
- Existing code passes the new formatter/linter on day one (fix violations as part of this change, not left for CI to discover).
- Land the actual "Step 6c" work that `harden-ci-pipeline` stubbed a placeholder for.

**Non-Goals:**
- End-to-end / integration tests (e.g. Playwright driving a real browser against a running backend) — this change is unit-level only.
- Test coverage *threshold enforcement* (e.g. failing CI below X% coverage) — not set up here. Coverage *reporting* is in scope (see Decisions) specifically so a future threshold decision has real baseline numbers instead of starting from zero; the report step never fails the build on its own.
- Auto-fixing formatting issues in CI (e.g. a bot that commits Prettier fixes) — CI only checks, contributors fix locally.
- Renegotiating `harden-ci-pipeline`'s job structure — this change extends its existing `frontend`/`test` jobs with additional steps, it doesn't add jobs, rename jobs, or touch `needs:`/trigger config.

## Decisions

**Frontend test runner: Vitest + React Testing Library + jsdom, over Jest.**
Both are viable and officially documented by Next.js for the App Router. Vitest chosen because: it reuses Vite's transform pipeline (faster cold start and watch mode than Jest's Babel/ts-jest transform), has near-drop-in Jest-compatible APIs (`describe`/`it`/`expect`/`vi.fn()` instead of `jest.fn()`) so React Testing Library docs/examples transfer directly, and needs less configuration to work with the TypeScript + ESM setup this project already uses (`next.config.mjs`, `"type"` not set to commonjs). Alternative considered: Jest — more battle-tested/ubiquitous, but slower and needs `next/jest` boilerplate for the Next.js-specific transform; no concrete requirement in this repo favors it over Vitest.

**Component test scope: real interaction tests for stateful/logic-bearing components, smoke-only for `SparkleHeader`.**
`ChatInterface.tsx` (state + fetch orchestration), `ChatInput.tsx` (controlled input + submit), `MessageBubble.tsx` (markdown rendering via `react-markdown`, conditional intent label), `MessageList.tsx` (maps messages, shows `ThinkingIndicator` when loading), and `ThinkingIndicator.tsx` (renders bounce animation state) all have behavior worth asserting. `SparkleHeader.tsx` is documented in `CLAUDE.md` itself as "decorative accents (no state)" — a full test suite for a component with no props, no state, and no conditional rendering would just assert "it rendered," which is what a smoke test already does. Writing more than that would be testing implementation detail (exact SVG paths, decorative positioning) that's expected to change freely.

**`ChatInterface.tsx` test isolation: mock `fetch`, not a running backend.**
Tests assert the request shape sent to `POST /chat` and the rendered result given a mocked JSON response — no real backend, no real network. Keeps frontend tests fast and independent of backend state, matching the "all tests are fully mocked" principle already established for the backend (`CLAUDE.md`'s lazy-init pattern).

**Backend `/chat` endpoint test: mock `api.main.graph`, not individual node functions.**
`api/main.py` builds `graph = build_graph()` once at import time. Tests patch `api.main.graph` (an `AsyncMock` with `ainvoke` returning a canned `AgentState`-shaped dict) rather than mocking `agent.nodes.get_model()` and letting the full graph run. This isolates what's actually new here — endpoint request/response shape, status codes, CORS headers — from agent routing logic, which is separately covered by `test_graph_routing.py` and the existing Step 4 test files. Confirmed safe to import `api.main` without a `GOOGLE_API_KEY`: `build_graph()` only wires `StateGraph` nodes/edges at compile time, it doesn't invoke any node, so the lazy `get_model()`/`get_vectorstore()` pattern (`CLAUDE.md`) isn't triggered at import time either.

**CORS test: assert the header via `TestClient`, not by re-reading the middleware config.**
`api/main.py` sets `allow_origins=["http://localhost:3000"]`. Test sends a request with `Origin: http://localhost:3000` and asserts `Access-Control-Allow-Origin` is echoed back; a second test with a mismatched origin asserts the header is absent. This tests behavior, not just that the line of config exists.

**Shared test render helper: `frontend/src/test-utils.tsx` exporting `renderWithProviders`, wrapping RTL's `render` with the app's real `Providers`.**
Production always mounts these components inside `<Providers>` (`frontend/src/app/providers.tsx`), which wraps `<ChakraProvider theme={theme}>` using the custom "unicorn" theme (`frontend/src/theme/index.ts` — custom color scales, `chatRadius`, fonts). Five of the six components under test (`ChatInterface`, `ChatInput`, `MessageBubble`, `ThinkingIndicator`, `SparkleHeader`) import `@chakra-ui/react` directly; `MessageList` doesn't import it itself but renders `MessageBubble`, which does — so it needs the same wrapper transitively. Using RTL's bare `render()` would mount every one of them without theme context, which either throws (components relying on theme-dependent hooks like `useColorModeValue` outside a provider) or silently falls back to Chakra's default theme (masking bugs in custom variants/tokens — a false pass, not a true one). `test-utils.tsx` re-exports RTL's other utilities alongside a `renderWithProviders` that wraps `ui` in the real `Providers` component (not a hand-rolled stand-in), so tests exercise the actual theme wiring, not a parallel approximation of it. Every component test file uses this helper instead of RTL's default `render`.

**Coverage reporting: `@vitest/coverage-v8` (frontend) + `pytest-cov` (backend), report-only.**
Both are added purely to produce numbers, not to gate anything. Frontend: `vitest run --coverage` using the `v8` provider (native, no extra instrumentation step, works with the jsdom setup already chosen). Backend: `pytest --cov=backend --cov-report=term`, one new dependency. Both are wired as additional steps inside the `frontend` and `test` jobs `harden-ci-pipeline` already defines — no new job, no threshold flags (no `--cov-fail-under`, no Vitest `coverage.thresholds`), so a drop in coverage never fails CI. This directly backs the Non-Goals note above: threshold enforcement is deferred, but only because there's now a baseline to set a threshold against later, not because the tooling doesn't exist yet.

**Backend formatter: `ruff format --check`, no new dependency.**
`ruff` is already installed and used for `ruff check`; `ruff format` ships in the same package. Just a new CI step and a new local command — zero new dependencies, minimal surface added.

**Frontend formatter: Prettier + `eslint-config-prettier`.**
Prettier is the de facto standard for this stack (TS/TSX/Next.js) and pairs with ESLint via `eslint-config-prettier`, which disables the small set of ESLint stylistic rules that would otherwise conflict with Prettier's own formatting. Config: `.prettierrc` with defaults reasonable for this codebase (no unusual options needed — the project doesn't have prior formatting conventions to preserve, since nothing has been auto-formatted yet).

**"Fix them" scope: run each new tool once, resolve findings, don't refactor beyond what's flagged.**
Per `CLAUDE.md`'s own guidance against unrelated cleanup — fixing formatter/linter findings means applying the tool's own fix where safe (`ruff format`, `prettier --write`) and manually resolving any ESLint/ruff-check findings that require judgment, not a broader pass over code style.

**Sequencing with `harden-ci-pipeline`.**
Both changes edit `.github/workflows/ci.yml`. This change assumes `harden-ci-pipeline` lands first (ESLint present, `frontend`/`test`/`build-*` jobs exist, placeholder `npm test` step present) and only adds format-check steps + swaps the test command — a small, low-conflict diff on top. If this change is implemented first instead, `tasks.md` notes where to check for/add the ESLint prerequisite so the frontend lint step this change's tests indirectly rely on (via `eslint-config-prettier` needing ESLint present) still works.

## Risks / Trade-offs

- **[Risk]** Two open changes (`harden-ci-pipeline`, this one) both touch `.github/workflows/ci.yml`; implementing them out of order or in parallel branches risks a merge conflict. → **Mitigation**: documented sequencing assumption above; recommend applying `harden-ci-pipeline` first.
- **[Risk]** Writing the first-ever frontend tests may surface that some components are harder to test than expected (e.g. Chakra UI + `framer-motion` animation timing in `ThinkingIndicator`). → **Mitigation**: RTL's `waitFor`/`findBy*` queries handle async rendering; if animation timing proves flaky, assert on the presence of the indicator's container/text rather than animation state.
- **[Risk]** "Fix existing violations" scope could balloon if Prettier/ESLint disagree heavily with current formatting across many files. → **Mitigation**: run formatters with their own auto-fix first (`ruff format`, `prettier --write`) which handles the bulk mechanically; manual fixes should be small in volume.
- **[Trade-off]** No coverage threshold enforcement — a future contributor could add an untested component and CI wouldn't catch it. Accepted for this change; revisit once a coverage baseline exists to set a sane, non-arbitrary threshold.

## Open Questions

- Should `docs/plan.md`'s stubbed "Step 6c: Frontend unit tests" title be renamed (e.g. "Step 6c: Testing, Linting & Formatting") to reflect the broader scope landed here, or should backend testing/formatting get its own "Step 6d"? Leaning toward renaming in place — the user's instruction was to land it all "as 6c" — but flagging since it changes what `harden-ci-pipeline`'s stub described.
- At archive time, if `harden-ci-pipeline`'s `ci-pipeline` capability and this change's `code-quality` capability both land, should they later be merged into one `ci-pipeline` spec, or stay separate (CI orchestration vs. what CI enforces)? No action needed now; noting for whoever archives these.
