## 1. Configuration

- [ ] 1.1 Add `CHAT_REQUEST_TIMEOUT_SECONDS` to `backend/api/main.py`, read via `os.environ.get(...)` the same way `DEPLOYMENT_ENVIRONMENT` is read at line 34, defaulting to `30`.
- [ ] 1.2 Document `CHAT_REQUEST_TIMEOUT_SECONDS` in `backend/.env.example` with a short comment giving the default and pointing at this change's `design.md` D1 for where the value comes from. Do not restate the measurement figures in that comment.
- [ ] 1.3 Resolve the open question on invalid/non-numeric `CHAT_REQUEST_TIMEOUT_SECONDS` values (fail fast at startup vs. silent fallback to default) before or during implementation — see `design.md` Open Questions. If it's not obviously low-stakes once you're looking at the code, raise it back rather than deciding silently.

## 2. Request Deadline

- [ ] 2.1 In the `/chat` handler in `backend/api/main.py`, wrap the existing `await graph.ainvoke(...)` call in `asyncio.wait_for(..., timeout=CHAT_REQUEST_TIMEOUT_SECONDS)`, inside the existing `try` block so the existing `finally` (duration recording, completion log) still runs on timeout.
- [ ] 2.2 Catch the timeout (`TimeoutError`) around the `wait_for` call and raise `fastapi.HTTPException(status_code=504, detail=...)`, leaving `intent`/`status` at their pre-set `"unknown"`/`"error"` defaults so the existing `finally` block records them unchanged.
- [ ] 2.3 Confirm no other exception path is altered — this change only adds a new `except` branch around the graph invocation; the existing `try`/`finally` structure and its `status="ok"`-set-last comment stay as-is.

## 3. Metrics

- [ ] 3.1 Add a new counter `chat_request_timeout_total` (no labels) in `backend/observability/metrics.py`, next to the existing instruments, with a `# TODO`-free description since this one ships with a recording call site from the start (unlike the two placeholder instruments).
- [ ] 3.2 Increment `chat_request_timeout_total` by 1 at the same call site that raises the 504 (task 2.2).
- [ ] 3.3 Seed `chat_request_timeout_total` at `0` from `seed_counters()`, alongside the existing seeded counters, so it's visible on `/metrics` immediately after startup.
- [ ] 3.4 Update `backend/observability/metrics.py`'s module docstring — it currently says "the four key Step 8 metrics"; it now declares five instruments and needs to say so accurately.
- [ ] 3.5 Update `docs/plan.md`'s four-metric framing to account for `chat_request_timeout_total`.
- [ ] 3.6 Do not touch `chat_request_duration_seconds`'s bucket boundaries in this change — record the deadline/boundary coupling (see `design.md` Decisions, D1) as a comment near the boundary list pointing at `openspec/changes/step8-observability-scaffold/tasks.md` Section 9, without re-tuning it here.

## 4. Tests

- [ ] 4.1 Add a test in `backend/tests/` that makes the mocked graph invocation hang past `CHAT_REQUEST_TIMEOUT_SECONDS` (e.g. patch `api.main.graph.ainvoke` to an `AsyncMock` whose side effect sleeps longer than a short test-scoped timeout override) and asserts the response is `504` with a JSON `detail` field.
- [ ] 4.2 In the same test, assert `chat_request_timeout_total` increments by 1 and `chat_request_duration_seconds` records `status="error"` for that request — no new `status` value appears.
- [ ] 4.3 Update `backend/tests/test_observability.py`'s seeded-counter assertions (`test_metrics_body_has_seeded_counters_not_histograms` or equivalent) to also assert `chat_request_timeout_total` is present and seeded at startup.
- [ ] 4.4 Run `pytest backend/tests/ -v` and confirm all tests pass, including the new ones. `.github/workflows/ci.yml` gates the backend job on `backend/**` changes, and this change touches `backend/`, so CI will run it.

## 5. Frontend Check

- [ ] 5.1 Check how `frontend/` currently renders a non-200 response from `POST /chat` (a 504 specifically). Determine whether the existing error-handling path (see `chat-frontend` spec's "Backend Unreachable Fallback" requirement) already produces an acceptable message for this case, or whether it needs a fix.
- [ ] 5.2 If the check in 5.1 finds a gap, fix it — scope is limited to that fix, not a broader frontend redesign. If no gap is found, record that finding (e.g. in this change's notes or a follow-up doc) rather than making a speculative change.
