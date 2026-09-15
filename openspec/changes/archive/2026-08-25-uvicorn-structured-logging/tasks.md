## 1. Shared JSON handler construction

- [x] 1.1 In `backend/observability/logging.py`, factor the `JsonFormatter` + `TraceCorrelationFilter` handler `configure_logging()` builds into a function that returns a new configured handler, so it can be attached to more than one logger without duplicating the construction.
- [x] 1.2 `configure_logging()` itself keeps attaching one such handler to the root logger, unchanged in behavior.

## 2. Startup-time reconfiguration of uvicorn's loggers

- [x] 2.1 Add a FastAPI startup hook in `backend/api/main.py` (an `@app.on_event("startup")` handler or the startup phase of a lifespan context manager — pick whichever this codebase's FastAPI version supports without a deprecation warning).
  - Used a `lifespan` context manager, not `@app.on_event`: this stack pins `fastapi==0.137.2`/`starlette==1.3.1`, where `on_event` is deprecated. `lifespan` carries the same ASGI guarantee D2 relies on — it runs once uvicorn's own `Server` has finished its setup.
- [x] 2.2 From that hook, attach a handler built via 1.1 to `logging.getLogger("uvicorn.access")` and `logging.getLogger("uvicorn.error")`, replacing their existing handler(s).
- [x] 2.3 Resolve the open question on `propagate` (`design.md` Open Questions) — either flip it to `True` and remove the loggers' own handlers, or leave it `False` and only swap the handler — before or during implementation.
  - Resolved: `propagate=False` on both, with the handler swapped. Reading uvicorn's actual `LOGGING_CONFIG` (`uvicorn.config.LOGGING_CONFIG`, checked directly rather than assumed) showed `uvicorn.error` has no handler and no explicit `propagate` of its own — it inherits Python logging's default `propagate=True` and reaches its parent `uvicorn` logger's plain-text handler that way. Attaching a handler to `uvicorn.error` without also forcing `propagate=False` would have produced two lines per message (ours, JSON, plus the inherited plain-text one via the parent). Setting `propagate=False` explicitly on both loggers avoids that regardless of each logger's starting state.
- [x] 2.4 Do not add any code that captures or attaches span context to these two loggers specifically — a null `trace_id`/`span_id` on their lines is the correct, expected outcome (`design.md` D3).
  - No such code was added. See 3.2 — this task's own premise (null is what happens) turned out to be only partly right; recorded there, not acted on further here.

## 3. Verification (live, not `pytest`)

- [x] 3.1 `docker-compose up --build` (a full stack start, not `uvicorn --reload`) and confirm via `docker-compose logs backend` that a `GET /health` or `GET /metrics` line — and a `POST /chat` access line — are now valid JSON, in the same shape as the application's own log lines.
  - Ran `docker-compose up --build -d backend` (backend only — `prometheus`/`grafana` were left untouched, per the standing prohibition on `docker-compose down -v`). New container started `2026-08-22T10:00:20Z`. First lines out:
    ```
    backend-1  | INFO:     Started server process [1]
    backend-1  | INFO:     Waiting for application startup.
    backend-1  | {"asctime": "2026-08-22 10:00:29,342", "levelname": "INFO", "name": "uvicorn.error", "message": "Application startup complete.", "trace_id": null, "span_id": null}
    backend-1  | {"asctime": "2026-08-22 10:00:29,345", "levelname": "INFO", "name": "uvicorn.error", "message": "Uvicorn running on http://0.0.0.0:8000 ...", "trace_id": null, "span_id": null}
    backend-1  | {"asctime": "2026-08-22 10:00:31,203", "levelname": "INFO", "name": "uvicorn.access", "message": "127.0.0.1:33430 - \"GET /health HTTP/1.1\" 200", "trace_id": null, "span_id": null}
    ```
    The two lines before the lifespan hook ran (`Started server process`, `Waiting for application startup`) are plain text — they come from the `uvicorn` logger itself, which this change deliberately does not touch. Every `uvicorn.error`/`uvicorn.access` line from `Application startup complete.` onward is JSON. Across 5 minutes of mixed `/health`, `/metrics`, and `/chat` traffic afterward, 33/33 `uvicorn.access`/`uvicorn.error` lines parsed as valid JSON (checked programmatically, not by eye).
  - **This is the answer to the ordering question D2 flagged as unverified: it holds.** The lifespan hook's reconfiguration was in effect before uvicorn logged its own `Application startup complete.` line, and stayed in effect for every request after. Nothing observed clobbered it.
- [x] 3.2 Confirm the JSON access line carries `trace_id`/`span_id` as `null` — not absent, not an error — consistent with `TraceCorrelationFilter`'s existing behavior outside a span.
  - **Confirmed for `/health` and `/metrics`, not confirmed for `/chat` — and the reasoning in `design.md` D3 does not hold as written.** `/health`/`/metrics` access lines carry `trace_id: null, span_id: null`, e.g. `{"asctime": "2026-08-22 10:02:01,969", ..., "name": "uvicorn.access", "message": "127.0.0.1:49040 - \"GET /health HTTP/1.1\" 200", "trace_id": null, "span_id": null}` — but that's because `FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")` means no span ever exists for those paths, not because a span closed before the line was logged.
    For `POST /chat`, which *is* instrumented, the access line carries the request's real `trace_id`/`span_id`, matching every other line that request emitted:
    ```
    backend-1  | {"asctime": "2026-08-22 10:00:56,987", "levelname": "INFO", "name": "api.main", "message": "chat request completed", "intent": "weather", "status": "ok", "duration_seconds": 6.518608585989568, "trace_id": "7624316686695c232b92342c9ed45563", "span_id": "c92da343e5ed65dd"}
    backend-1  | {"asctime": "2026-08-22 10:00:56,987", "levelname": "INFO", "name": "uvicorn.access", "message": "192.168.97.1:57856 - \"POST /chat HTTP/1.1\" 200", "trace_id": "7624316686695c232b92342c9ed45563", "span_id": "c92da343e5ed65dd"}
    ```
    Reproduced on a second, independent `/chat` request (different message, different trace_id) with the identical pattern. D3's premise was that the FastAPI-instrumentation span has already ended by the time uvicorn logs the access line, so `TraceCorrelationFilter` would find no current span and record `null` — as it did for the *previous*, plain-text version of this line, but only because that line never went through `TraceCorrelationFilter` at all (item 8/pass 1b's finding was "not JSON", not "JSON with null `trace_id`"). This is the first time that filter has actually run against a `uvicorn.access` record, and for an instrumented path, the span context Starlette's OTel middleware opened is still current at that point — the access line is a genuine, correctly-correlated part of the request's log lines, not a null-trace_id line as `design.md` predicted. Not fixed or adjusted here — `design.md` and the spec's `Uvicorn's access line for a completed request` scenario both assert null unconditionally, and that assertion is now contradicted by observation for instrumented paths. Flagged for the change owner rather than edited silently, per this repo's working agreement.
- [x] 3.3 Confirm the fix survives a second request in the same process (not just the first one after startup), ruling out the "clobbered later" risk in `design.md`.
  - Confirmed: two separate `/chat` requests, two `/health` requests, and two `/metrics` requests all produced JSON access lines across a 5-minute window, all after the same single lifespan-hook invocation at startup. Nothing re-clobbered the handler.
- [x] 3.4 Record the verification output somewhere durable (this change's own notes, or wherever this project keeps such evidence) — do not rely on memory of having checked it once.
  - Recorded above, in 3.1–3.3, with the raw log lines rather than a paraphrase.

## 4. Regression check

- [x] 4.1 `pytest backend/tests/ -v` still green. This is a regression check only — per `design.md`, no test in this suite can exercise the behavior being added, since `TestClient` never starts a real uvicorn `Server`.
  - 77 passed. One pre-existing, unrelated warning (`StarletteDeprecationWarning` on `httpx`-backed `TestClient`) and one pre-existing, unrelated stderr trace from a background `BatchSpanProcessor` export thread hitting a closed stream at interpreter shutdown — neither touches logging and both reproduce independently of this change.
- [x] 4.2 `ruff check backend/` and `ruff format --check backend/` clean.
  - `ruff check backend/`: "All checks passed!". `ruff format --check backend/`: "26 files already formatted".
