## 1. Shared JSON handler construction

- [ ] 1.1 In `backend/observability/logging.py`, factor the `JsonFormatter` + `TraceCorrelationFilter` handler `configure_logging()` builds into a function that returns a new configured handler, so it can be attached to more than one logger without duplicating the construction.
- [ ] 1.2 `configure_logging()` itself keeps attaching one such handler to the root logger, unchanged in behavior.

## 2. Startup-time reconfiguration of uvicorn's loggers

- [ ] 2.1 Add a FastAPI startup hook in `backend/api/main.py` (an `@app.on_event("startup")` handler or the startup phase of a lifespan context manager — pick whichever this codebase's FastAPI version supports without a deprecation warning).
- [ ] 2.2 From that hook, attach a handler built via 1.1 to `logging.getLogger("uvicorn.access")` and `logging.getLogger("uvicorn.error")`, replacing their existing handler(s).
- [ ] 2.3 Resolve the open question on `propagate` (`design.md` Open Questions) — either flip it to `True` and remove the loggers' own handlers, or leave it `False` and only swap the handler — before or during implementation.
- [ ] 2.4 Do not add any code that captures or attaches span context to these two loggers specifically — a null `trace_id`/`span_id` on their lines is the correct, expected outcome (`design.md` D3).

## 3. Verification (live, not `pytest`)

- [ ] 3.1 `docker-compose up --build` (a full stack start, not `uvicorn --reload`) and confirm via `docker-compose logs backend` that a `GET /health` or `GET /metrics` line — and a `POST /chat` access line — are now valid JSON, in the same shape as the application's own log lines.
- [ ] 3.2 Confirm the JSON access line carries `trace_id`/`span_id` as `null` — not absent, not an error — consistent with `TraceCorrelationFilter`'s existing behavior outside a span.
- [ ] 3.3 Confirm the fix survives a second request in the same process (not just the first one after startup), ruling out the "clobbered later" risk in `design.md`.
- [ ] 3.4 Record the verification output somewhere durable (this change's own notes, or wherever this project keeps such evidence) — do not rely on memory of having checked it once.

## 4. Regression check

- [ ] 4.1 `pytest backend/tests/ -v` still green. This is a regression check only — per `design.md`, no test in this suite can exercise the behavior being added, since `TestClient` never starts a real uvicorn `Server`.
- [ ] 4.2 `ruff check backend/` and `ruff format --check backend/` clean.
