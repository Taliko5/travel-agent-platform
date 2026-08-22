## Context

`step8-observability-scaffold` left four metric instruments declared with no recording call sites, no label sets and provisional bucket boundaries, on the stated grounds that low-cardinality label design was itself the learning objective. This change is that work. Two of the four instruments are now recorded; two are still declared and unrecorded.

The authoritative detail lives in two places and is deliberately not repeated here. Each panel's expression, the reasoning behind it and the measurement figures it quotes live in that panel's own `description` field in `observability/grafana/dashboards/travel-agent-overview.json`, which is where a reader meets them; `observability/grafana/dashboards/README.md` covers what makes a dashboard file provisionable. This change's `tasks.md` owns the per-item history — the seeding defect's root cause, the bucket measurements, and the decisions taken along the way. A second copy of those numbers is what produced the 2026-08-11 / 2026-08-12 discrepancy already recorded there.

## Goals / Non-Goals

**Goals:**
- Make the four key metrics named in `docs/plan.md` real: recorded, labelled, and queryable.
- Keep label cardinality bounded and justified rather than incidental.
- Make a metric's absence from `/metrics` mean something definite, rather than being ambiguous between "not seeded" and "never happened".
- Give the dashboard a stable contract to build on, so panel expressions do not have to be revised every time the instrumentation changes.

**Non-Goals:**
- Instrumenting anything the scaffold did not already declare.
- Alerting.
- Changing the agent's behaviour. Every recording site is additive and must not alter `AgentState` or exception propagation.

## Decisions

### D1 — `status` carries exactly two values, `ok` and `error`
A timed-out, failed or otherwise unsuccessful request records `status="error"`; nothing else is ever produced.

This is load-bearing rather than stylistic. The dashboard's error-rate panel filters `chat_request_duration_seconds_count{status="error"}` exactly, and the latency-percentile panels filter `{status="ok"}` on the grounds that the error-rate panel still counts what they exclude. A third value would remove those requests from both. `chat-request-deadline` relies on this invariant too — its own spec forbids introducing a `status="timeout"`.

### D2 — Counters are seeded at zero; histograms never are
`seed_counters()` runs from `backend/api/main.py` after `set_meter_provider()`. Ordering is a functional requirement, not a style preference: instruments created before a provider is installed are OTel proxies, and measurements recorded on a proxy are dropped silently. Reordering imports does not fix it, because any import of the graph pulls `metrics.py` in first.

Counters are seeded because a counter that exists at zero records a starting point; without one, Prometheus first observes the series already at some value and the increase up to it is invisible to `rate()`. It also makes a query answer "0" rather than "No data".

Histograms are deliberately left unseeded. A `.record(0)` would inject a permanent observation of zero seconds that skews `histogram_quantile()` and `rate(_sum)/rate(_count)` from the first scrape onward. The consequence — that a histogram series does not exist until real traffic creates it — is accepted, and the dashboard's expressions are written to tolerate it.

### D3 — `rag_retrieval_total` keeps a label-less zero
It has no recording call sites, no label set and no panel. A label-less zero is a truthful statement that no retrieval has happened. Inventing labels for it would manufacture series that no code can ever produce. Re-seed it with real label combinations when its call sites are decided; not before.

### D4 — The dashboard is file-provisioned and two of its expressions are frozen
`observability/grafana/dashboards/travel-agent-overview.json` is a raw dashboard model loaded by Grafana's file provider, not an API wrapper object, so it can be dropped into the provisioning path and version-controlled. Confirmed provisioned on 2026-08-18 via Grafana's API reporting `meta.provisioned: true`.

The error-rate and classifier-fallback panels wrap their numerators — and only their numerators — in `or vector(0)`. That placement was verified against live data and is not open to revision; each of those two panels' `description` records why.

The heatmap panel needs two settings that nothing in its rendered output will tell you are missing: `"format": "heatmap"` on the Prometheus target, and `"calculate": false` in the panel options. The first is what makes the datasource sort series by `le` and convert Prometheus' cumulative buckets into the per-bucket counts a heatmap needs; the second stops Grafana re-bucketing values that are already bucketed. Omit either and the panel still draws — as a plausible picture in which every row above the data is darker than the one below it. It is wrong, and it does not look wrong.

### D5 — Bucket boundaries are provisional and get one measured re-tune
The scaffold's boundaries were a guess. They are re-tuned once, from an actual latency distribution, rather than repeatedly. `llm_call_duration_seconds` must not copy `chat_request_duration_seconds`'s boundaries — it measures a component of a request, not a request — and gets its own coarse set, measured, then tuned once.

### D6 — Load is generated by a committed script, not by hand
`rate()` needs several scrape intervals of data before any panel reads as anything but broken. The script's defaults are a rate limit rather than a performance setting, and its output is preserved to a file: the 2026-08-12 run's stdout was not saved, and reconstructing what happened then had to be done from Prometheus instead.

### D7 — Request-level log correlation is scoped to the application's own logger, while its span is active
`Trace and Log Correlation for a Single Request`'s original wording — "each log line it emits SHALL carry a non-null `trace_id`" — contradicted the scaffold's own `Structured Logging with Trace Correlation`, which explicitly permits a null `trace_id` for a log emitted outside any active span, "rather than causing an error." Pass 1b of the 9-d verification (2026-08-21) found a line without the request's `trace_id` on a real request: `uvicorn`'s access line for a `/chat` request, the only one of seventeen that request produced without it. The other sixteen — application-logger JSON and OTel span-export blocks alike — all carried it, and all agreed on its value.

The reason given for that line lacking a `trace_id` was wrong, and is corrected here (2026-08-22) rather than left to mislead. It was not that the line is emitted outside the request's span; uvicorn emits it from inside the ASGI send path, where the span is still current. It lacked one because `propagate=False` kept that line away from the handler carrying `TraceCorrelationFilter` — it was not JSON at all, so nothing ever stamped it. Once `uvicorn-structured-logging` routes it through that handler, the same line carries the request's `trace_id` and `span_id`. The narrowing below still stands: it turns on which lines reach the application's configured handler while a span is active, which is a boundary that holds whatever the access line happens to do.

The scenario now reads "each log line the application's own logger emits while the request's span is active," which is what pass 1b's evidence demonstrated the system actually does, and it no longer contradicts the scaffold's scenario: the one line it excludes is precisely the one the scaffold's own wording already carves out.

**This narrows a contradiction between two requirements; it does not make either requirement pass in full.** The scaffold's `Structured Logging with Trace Correlation` requirement says "the system SHALL emit backend logs in structured (JSON) format" — unqualified, covering `uvicorn.access` and `uvicorn.error` as much as the application's own logger. Item 8 of the 9-d verification recorded why they don't: both have `propagate=False` and handlers of their own, so their output never reaches `configure_logging()`'s JSON formatter at all. That output is not JSON with a null `trace_id` — the scaffold's own documented "outside a span" case — it is plain text, a different failure the scaffold's requirement does not survive as written. Rewording this change's scenario relocated the contradiction onto the scaffold's requirement rather than resolving it; that requirement is still unmet, and fixing it — reconfiguring or wrapping `uvicorn.access`/`uvicorn.error` so their output is JSON too — is left to a separate change. Do not read D7 as that requirement having been relaxed until it passed: it was never touched, and it still fails.

### D8 — Fixing D7's leftover fails by converting `uvicorn.access`/`uvicorn.error` to JSON, not by switching them off

Two ways to close the gap D7 left open. Switch the two loggers off (`access_log=False`, or silence them directly), or reconfigure them to emit JSON through the same formatter the application's own logger uses.

Switching off is cheaper, and its effect is certain — the plain-text lines item 8 found simply stop existing. It is also the more expensive choice long-term, because uvicorn's access line is currently the *only* record, at the log level, of three distinct things:
1. A request that never reaches the application's own handler at all — malformed input, a route nothing matches, anything ASGI rejects before routing ever runs the endpoint function. The application's logger never executes for these; there is nothing else to log them.
2. `/health` and `/metrics` traffic. `Self-Observation Excluded from Tracing` deliberately keeps this traffic out of spans, on purpose — so with the access log off too, it would leave no trace anywhere in the container's own output. (Prometheus's `up` series and the compose healthcheck's own pass/fail state still exist independently of logs, so this loss is partial, not total — but neither of those tells you what path or status code actually crossed the wire, which a log line does.)
3. The status code actually sent to the client, which is not always the status the handler recorded. FastAPI validates a declared `response_model` *after* the endpoint returns; if that validation fails, the client receives a `500` the handler's own code never saw, while `chat_request_duration_seconds{status="ok"}` — recorded inside the handler, before validation runs — would still read `ok`. Uvicorn's access line is the only place that specific discrepancy could ever be seen.

Converting keeps all three, and it is what Step 9's line-oriented-JSON log-shipping premise already assumes true. What it rests on has not been checked: `configure_logging()` runs at `backend/api/main.py:61`, at import time — when uvicorn imports `api.main` to resolve the ASGI callable — while `uvicorn.access`/`uvicorn.error` get their own handlers from uvicorn's own logging setup, which runs when its `Server` starts. Which one runs first, and so whether anything `configure_logging()` did to those two loggers would survive uvicorn's own setup running after it, is unverified against this repository.

**Decision: convert, not switch off.** What switching off destroys is real, and the third case is load-bearing — it is the one discrepancy this change's own metrics structurally cannot surface, because the metric is recorded before the failure that would invalidate it. The ordering question is a thing to check, not a reason to default to the lossy option: this codebase already hit the identical shape of problem in D2 (an OTel counter seeded before `set_meter_provider()` installed a real provider, silently dropped) and fixed it the same way — not by reordering imports, but by moving the dependent call out of import time into a hook guaranteed to run after the thing it depends on exists. The same move applies here: reconfigure `uvicorn.access`/`uvicorn.error` from a FastAPI startup hook rather than from `configure_logging()` at import, since a startup hook is guaranteed to run after uvicorn's `Server` has already finished its own logging setup, not before. That construction is what makes conversion trustworthy rather than merely hoped-for — but it is a plan, not yet a checked fact, and implementing it must confirm the reconfigured loggers actually emit JSON before this decision is treated as closed.

## Risks / Trade-offs

- **[Risk]** Label cardinality grows silently as intents or statuses are added → **Mitigation**: `VALID_INTENTS` is a single module constant shared by the classifier and the seeding loop, so adding an intent cannot quietly desynchronise the two; `status` is fixed at two values by D1.
- **[Risk]** A histogram series that does not exist until traffic occurs makes a healthy dashboard read "No data" → **Mitigation**: the affected panel expressions guard their numerators, per D4.
- **[Risk]** The dashboard's expressions and the instrumentation's label sets are coupled but declared in different files, with nothing enforcing the link → **Mitigation**: recorded here and in the panel descriptions themselves; not automated.
- **[Risk]** Nothing under `scripts/` or `observability/` is exercised by CI, so a broken dashboard JSON or load script is only caught by hand → **Mitigation**: none in this change. Recorded as an open item.

## Open Questions

- **Span names and attributes.** Which request and response data belongs on the `classify_intent` chain span, the `generate_response` chain span, and the LLM-call span nested within it. Not started.
- **`llm_call_duration_seconds` and `rag_retrieval_total` call sites.** Both instruments are declared and unrecorded. Their label sets follow from where they are recorded, which has not been decided.
- **CI coverage for `scripts/` and `observability/`.** Whether to extend `dorny/paths-filter` to those paths, and what would run if it did.
- **Whether `Prometheus Scrapes the Backend Successfully` is an addition or a supersession.** The scaffold's `Prometheus-Scrapable Metrics Endpoint` requires `GET /metrics` to return `200`. This change's requirement covers the same target but tolerates a redirect. If the backend answers `/metrics` with a redirect rather than with the metrics, the scaffold's requirement is false as written, and this one supersedes it rather than adding to it. Item 2 of the 9-d verification produces that evidence; the decision waits on it.
- **The scaffold's `Structured Logging with Trace Correlation` requirement does not hold.** Resolved as D7: `uvicorn.access`/`uvicorn.error` never reach `configure_logging()`'s JSON formatter (`propagate=False`, handlers of their own), so their output is plain text, not JSON — a requirement failure distinct from, and not excused by, the scaffold's own "null `trace_id` outside a span" allowance. This change narrowed its own request-correlation scenario so it stops contradicting the scaffold's, per D7; it does not fix the scaffold's requirement. D8 decides *how* the fix should go — convert, via a FastAPI startup hook, not switch off — but implementing and verifying it is left to a separate change.
