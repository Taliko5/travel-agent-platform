## Context

`backend/observability/logging.py` configures the root logger with a `JsonFormatter` and a `TraceCorrelationFilter` that stamps `trace_id`/`span_id` from the active OpenTelemetry span onto every record, or `None` for both when no span is active. `backend/api/main.py:61` calls `configure_logging()` at module import time, alongside the rest of that file's import-time OTel/metrics wiring.

`uvicorn.access` and `uvicorn.error` are configured by uvicorn itself, independently of `configure_logging()`: both have `propagate=False` and handlers of their own, installed by uvicorn's default logging config. Item 8 of `step8-metric-design`'s 9-d verification recorded this as the reason the container's stdout interleaves JSON application logs with plain-text uvicorn lines. Pass 1b of the same verification (`docs/step8-9d-evidence.md`) enumerated all 17 log records one `/chat` request emits between receipt and the response leaving the server: 16 carried the request's `trace_id`; the 17th — uvicorn's own access line — did not, and was not JSON at all.

`step8-metric-design`'s `design.md` carries the decisions this change executes:
- **D7** narrowed that change's own `Trace and Log Correlation for a Single Request` scenario to the application's own logger while its span is active, so it stops contradicting the scaffold's "null `trace_id` outside a span is fine" scenario — and states plainly that doing so relocates, rather than fixes, the scaffold's own `Structured Logging with Trace Correlation` requirement, which remains unmet.
- **D8** weighs switching `uvicorn.access`/`uvicorn.error` off against converting them to JSON, and decides to convert — because switching off destroys the only log-level record of three things (a request that never reaches the application handler, `/health`/`/metrics` traffic, and the status actually sent to the client when it diverges from what the handler recorded) — while flagging the fix's central risk as unverified: whether `configure_logging()`, run at import time, can reliably reconfigure loggers that uvicorn itself sets up when its `Server` starts, given the two events aren't obviously ordered by import position alone.

This change does not re-derive either decision; it designs the mechanism D8 named but did not specify.

## Goals / Non-Goals

**Goals:**
- Make `uvicorn.access` and `uvicorn.error` emit through the same JSON formatter as the rest of the backend's logs.
- Preserve `TraceCorrelationFilter`'s existing behavior unchanged, including on the access line: null `trace_id`/`span_id` when no span is active is correct, not a defect, per the scaffold's own spec.
- Make the fix's ordering hold by construction — proven to run after uvicorn's own logging setup — rather than by an assumption about import timing.

**Non-Goals:**
- Switching `uvicorn.access`/`uvicorn.error` off. Decided against in `step8-metric-design`'s D8; not reopened here.
- Injecting a non-null `trace_id` into a log line emitted outside any active span, by middleware or otherwise. Out of scope by the proposal's own instruction, and unnecessary: the scaffold's spec already treats a null value there as correct.
- Anything to do with `step8-metric-design`'s own request-level log-correlation scenario, already resolved by its D7.
- CloudWatch log shipping (Step 9) — only removing the obstacle to its line-oriented-JSON premise, not building the shipping itself.

## Decisions

### D1 — Convert, not switch off (carried from `step8-metric-design` D8)
Not re-weighed here. The full comparison — what each of the three things switching off destroys, and why converting satisfies Step 9's line-oriented-JSON premise instead — lives in `openspec/changes/step8-metric-design/design.md`, D8. This change exists to build what D8 decided, not to re-litigate whether it was the right call.

### D2 — Reconfigure from a FastAPI startup hook, not from `configure_logging()` at import time
`configure_logging()` runs at `backend/api/main.py:61`, at import time — when uvicorn imports `api.main` to resolve the ASGI callable. `uvicorn.access`/`uvicorn.error` get their handlers from uvicorn's own logging setup, which runs when its `Server` starts. Which happens first is the fact D8 left unverified, and it matters: if uvicorn's setup runs *after* whatever this change does to those two loggers, it would silently overwrite the reconfiguration, and the fix would appear to work under casual testing (a single `uvicorn --reload` run where import happens to come last) while failing under the exact `docker-compose` startup path production actually uses.

Rather than resolving that question by reading uvicorn's internals and trusting it holds across versions, this change sidesteps it the same way `step8-metric-design`'s D2 fixed an identical-shaped bug (`seed_counters()` moved out of import time into a hook run after `set_meter_provider()` installed a real provider, because instruments touched before that point are silently-dropping OTel proxies): reconfigure `uvicorn.access`/`uvicorn.error` from a FastAPI startup hook (`@app.on_event("startup")` or the startup phase of a lifespan context manager). ASGI guarantees a startup hook fires only once the server that's hosting the app — uvicorn's `Server`, already fully configured, including its own logging — has finished its own setup and is ready to accept connections. Nothing run from that hook can be clobbered by uvicorn's own setup running later, because uvicorn's own setup necessarily already ran.

Concretely: expose the JSON handler `configure_logging()` builds (the `JsonFormatter` + `TraceCorrelationFilter` pairing) as something the startup hook can attach to `logging.getLogger("uvicorn.access")` and `logging.getLogger("uvicorn.error")` in place of their existing handlers — reusing the same construction rather than duplicating it, so the two logging paths cannot drift out of format independently.

Whether `propagate` on those two loggers should flip to `True` (letting them fall through to root, removing their own handler entirely) or stay `False` with just the handler swapped is left to Open Questions — both produce JSON; the difference is a code-organization preference, not a behavioral one this design needs to settle.

### D3 — `TraceCorrelationFilter` is left alone, and what it stamps on the access line follows from whether a span exists
`TraceCorrelationFilter` already does the right thing, and the scaffold's own `Structured Logging with Trace Correlation` spec says so explicitly (`Scenario: A log is emitted outside any active span`: fields present but null, not an error). Nothing here changes it.

**Corrected 2026-08-22, from the implementation's own live check.** This decision originally predicted a null `trace_id` on every access line, reasoning that uvicorn logs it after the ASGI application has returned, once the request's span has ended. That reasoning was wrong, and so was the prediction. Uvicorn emits the access line from inside the ASGI send path — the application itself drives it — so on an instrumented route the request's span context is still current, and the line carries the request's own `trace_id` and `span_id`, matching the rest of that request's lines including the `span_id`. Null appears only on `/health` and `/metrics`, and not because a span closed: `excluded_urls` means no span is ever created for them.

Pass 1b's finding is unaffected but was described imprecisely afterwards. What it observed was a line that was not JSON at all — a line that never reached `TraceCorrelationFilter`, because `propagate=False` kept it away from the handler that carries the filter. It was never "JSON with a null `trace_id`". This change is the first time that filter has run against a `uvicorn.access` record.

The practical consequence is that the access line is a correctly correlated part of a traced request's log lines rather than an orphan, and no work is needed to make it so. Capturing span context to survive past a span's lifetime — request-scoped middleware or similar — remains ruled out, and is now also unnecessary.

## Risks / Trade-offs

- **[Risk]** The startup-hook's guarantee is that it runs after uvicorn's *initial* logging setup — not that uvicorn never touches those loggers again afterward (for instance, on whatever `--reload` does when it restarts the worker process). → **Mitigation**: verify directly against `docker-compose logs backend` — a full `docker-compose up`/restart, not a local `--reload` cycle — that JSON output on the access line persists across more than one request, the way pass 1b verified the original defect. Treat D2 as unconfirmed until that check runs.
- **[Risk]** No automated test can exercise this: `TestClient` never starts a real uvicorn `Server`, so `uvicorn.access`/`uvicorn.error` never fire under `pytest`. → **Mitigation**: none available within this change's means; recorded as a permanent gap rather than a deferred task. Manual/live verification is the only method, consistent with how `step8-metric-design`'s 9-d procedure already treats other stack-level behavior.
- **[Risk]** Reusing `configure_logging()`'s handler construction for a second purpose (uvicorn's loggers, not just root) couples the two call sites; a future change to the formatter that only updates one of them could reintroduce a format mismatch between the app's own logs and uvicorn's. → **Mitigation**: share one handler-building function rather than writing the JSON handler twice, per D2.

## Migration Plan

Additive, in-process only: existing plain-text `uvicorn.access`/`uvicorn.error` lines become JSON lines carrying the same information (address, method, path, status) plus null `trace_id`/`span_id`. Nothing today parses the old plain-text shape as a contract — item 8's own finding treated the interleaving as a problem for Step 9's premise, not as something relied upon. No persisted state, no data migration. Rollback is reverting the deploy.

## Open Questions

- **`propagate=False` + handler swap, vs. `propagate=True` + handler removal.** Both make the two loggers' output JSON; which is the better fit for this codebase's existing logging setup is not decided here.
- **Whether the "startup hook runs once, after initial setup" guarantee is enough**, or whether a periodic self-check (e.g., re-asserting the handler on some interval, in case something resets it later in the process lifetime) is warranted. No evidence of anything resetting it exists yet; not adding one preemptively unless the live verification in Risks finds a reason to.
- **Whether a docker-based integration test belongs in CI** to cover behavior `pytest`'s `TestClient` structurally cannot reach, or whether live verification at deploy time (as done here and in the 9-d procedure) is treated as sufficient going forward. Left for whoever picks this up to decide, or raise back if it's judged to matter.
