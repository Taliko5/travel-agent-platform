## Context

`backend/api/main.py`'s `/chat` handler (lines 102-138) wraps `await graph.ainvoke(...)` in a `try`/`finally` that always records `chat_request_duration_seconds` and a `chat request completed` log line, with `intent` defaulting to `"unknown"` and `status` defaulting to `"error"` until the graph call succeeds. Nothing today bounds how long that `await` can take. On 2026-08-12, five consecutive requests each spent 34-35 seconds inside `google_genai`'s internal `tenacity` retry loop before it gave up — the retry policy, not `/chat`, was what stopped them, and that policy bounds calls that fail rather than calls that hang. A sixth request from that run was recorded at 1025.74 seconds and was originally read here as the same loop running unchecked for seventeen minutes; that was wrong, and 999 of those seconds were a macOS Clamshell Sleep. `docs/step8-host-network.md` records the correction and closes the host-network question. This change does not depend on that incident: it addresses the structural fact that `/chat` imposes no ceiling of its own, so the bound on a slow request is whatever a third-party library's retry policy happens to be.

`backend/observability/metrics.py` currently declares and seeds `chat_request_duration_seconds` (histogram) and `intent_classification_total` (counter), with `llm_call_duration_seconds` and `rag_retrieval_total` declared but unrecorded. Its module docstring and `docs/plan.md` both describe "the four key Step 8 metrics." Panel 4 of `observability/grafana/dashboards/travel-agent-overview.json` (`docs/step8-task9c9d.md` lines 216-219) computes error rate by filtering `chat_request_duration_seconds_count{status="error"}`, and that panel's design explicitly accepts that slow failures fall out of the latency-percentile panels (panel 1) because panel 4 still counts them by status — an invariant recorded at `docs/step8-task9c9d.md` lines 224-225: `status` is only ever `ok` or `error`.

Section 9 of `openspec/changes/step8-observability-scaffold/tasks.md` records an agreed-but-not-yet-applied replacement bucket set for `chat_request_duration_seconds` that includes a `30.0` boundary.

## Goals / Non-Goals

**Goals:**
- Bound the total wall-clock time of a `/chat` request, regardless of which internal call is slow.
- Make a timed-out request observable as a distinct signal on `/metrics`, without disturbing the existing `status` invariant that panel 4 depends on.
- Keep the deadline configurable per-environment without a code change.

**Non-Goals:**
- Fixing the host network failures that triggered the 2026-08-12 incident (`docs/step8-host-network.md`).
- Tuning `google_genai`'s retry/backoff policy.
- Per-node or per-LLM-call timeouts inside the graph.
- Introducing a third `status` value, or otherwise classifying failure reasons beyond timeout vs. everything else.
- Redesigning the frontend's error handling — only a check for how it currently renders a non-200 `/chat` response, with a fix in scope only if that check finds a problem.

## Decisions

### D1 — Deadline value: 30 seconds, via `CHAT_REQUEST_TIMEOUT_SECONDS`
Read the same way `DEPLOYMENT_ENVIRONMENT` is read at `backend/api/main.py:34` (`os.environ.get(...)`, with a default), and documented in `backend/.env.example`.

Rationale: the largest successful request observed on 2026-08-12 was 13.15s, and 30s is roughly 2.3x that — generous enough not to cut off legitimate slow requests under normal conditions, while still finite. The per-intent latency figures from that run live in `docs/step8-task9c9d.md` and are deliberately not repeated here; only the maximum bears on this decision. 30.0 also coincides with a boundary in the bucket-boundary replacement set proposed at Section 9 of `openspec/changes/step8-observability-scaffold/tasks.md`, so a request that hits the deadline lands on a bucket edge in `chat_request_duration_seconds` and is visible as a distinct pile rather than smeared across an interpolated bucket. The controlled re-run of 2026-08-19 produced a maximum of 8.22s across 60 requests, so 30s remains comfortably above anything observed under healthy conditions.

**Coupling, recorded not resolved**: this value and that bucket boundary set were chosen with each other in mind but are declared in two different places (an environment variable here, a histogram boundary list in `metrics.py`). If either changes, the other should be revisited — nothing enforces this at the code level.

Alternatives considered: a shorter deadline (e.g. 15s) would cut into the legitimate weather-intent tail (up to 13.15s observed); a longer one weakens the guarantee this change exists to provide. Not evaluated further — 30s was supplied as the decision, not derived here.

### D2 — Placement: wrap the whole graph invocation with `asyncio.wait_for`
`asyncio.wait_for(graph.ainvoke(...), timeout=CHAT_REQUEST_TIMEOUT_SECONDS)`, replacing the current bare `await graph.ainvoke(...)`.

Rationale: per-LLM-call timeouts would not bound total request time — the graph has four nodes, and `google_genai`'s tenacity retries happen *inside* a single call, invisible from outside it. Wrapping the whole invocation is the only construct that makes the user-observed duration finite regardless of which node or call is slow.

`asyncio.wait_for` cancels the inner coroutine on expiry (raising `CancelledError` inside it), which is what actually stops the retry loop rather than merely stopping the caller from waiting for it. `OTelCallbackHandler`'s span dict is already bounded (`docs/step8.md`) specifically because `*_end`/`*_error` callbacks aren't guaranteed to fire on cancellation, disconnect, or timeout — so a cancelled graph run's orphaned spans are reclaimed by the existing eviction path, not leaked. No change to `callback_handler.py` is implied by this decision.

Mechanically, this means catching the timeout around the `wait_for` call specifically (`except TimeoutError` — `asyncio.TimeoutError` is an alias of the builtin `TimeoutError` as of the Python version already pinned for this backend), inside the existing `try` so the existing `finally` block still runs and still records `chat_request_duration_seconds` and the completion log line for the timed-out request.

### D3 — Response: HTTP 504 Gateway Timeout, JSON `detail` body
Raise `fastapi.HTTPException(status_code=504, detail=...)` from the `except TimeoutError` branch, which FastAPI serializes as `{"detail": "..."}` — no custom response schema.

Rationale: the upstream did not respond in time, and that is what 504 means. Returning `200` with an apology in the `response` field would make access logs — and any future CloudWatch view — report the request as a success.

Scope note: whether the frontend today renders a non-200 `/chat` response acceptably is unknown and is a check task, not assumed here (see Open Questions).

### D4 — Metrics: `status` stays `ok` | `error`; new label-less counter for timeouts
A timeout is recorded as `status="error"` on the existing `chat_request_duration_seconds` histogram — no new `status` value.

Rationale, not a preference: panel 4's expression (`docs/step8-task9c9d.md` lines 216-219) filters `status="error"` exactly; panel 1's design (lines 151-155) explicitly accepts losing slow failures from the latency percentiles *because panel 4 still counts them* by status; lines 224-225 record "`status` is only ever recorded as `ok` or `error`" as an invariant the panel-4 reasoning depends on. Introducing `status="timeout"` would silently remove timeouts from the error-rate panel that exists specifically to catch them.

To distinguish timeouts without touching `status`, add one new instrument: `chat_request_timeout_total`, a counter with **no labels**, seeded at 0 from `seed_counters()` in `backend/observability/metrics.py` alongside the existing seeded counters. A label-less zero is the case `openspec/changes/step8-observability-scaffold/tasks.md` line 67 explicitly endorses: it truthfully states that no timeout has occurred yet. A labelled `reason` counter was considered and rejected — two of its plausible values (e.g. distinguishing timeout from other error subtypes) would have no recording call site, which the same tasks.md line 67 reasoning forbids (a label combination that can never be produced is worse than no label at all).

Consequence: `backend/observability/metrics.py`'s module docstring ("the four key Step 8 metrics") and `docs/plan.md`'s four-metric framing both become inaccurate once a fifth instrument exists, and need a wording update — not a redesign of either document.

## Risks / Trade-offs

- **[Risk]** A 30s ceiling may still cut off a rare, legitimately slow request that would have succeeded at 31s → **Mitigation**: the value is overridable per-environment via `CHAT_REQUEST_TIMEOUT_SECONDS` without a code change; 30s was chosen as ~2.3x the worst observed successful request, not the median.
- **[Risk]** `asyncio.wait_for` cancels the awaiting coroutine, but cancellation does not guarantee the underlying outbound HTTP connection to Gemini is torn down instantly — the request may continue consuming resources briefly after the client-visible timeout fires → **Mitigation**: accepted as-is; tuning `google_genai`'s own retry/timeout behavior is an explicit non-goal of this change.
- **[Risk]** The deadline value and the `chat_request_duration_seconds` bucket-boundary set are coupled by intent (both reference 30.0) but not by code — a future change to one with no memory of the other silently breaks the "timeouts land on a bucket edge" property → **Mitigation**: documented here and in the proposal; no automated enforcement is in scope.
- **[Risk]** Adding a fifth metric instrument invalidates the "four key metrics" framing wherever it's asserted in prose → **Mitigation**: tracked as an explicit task to update `metrics.py`'s docstring and `docs/plan.md`.

## Migration Plan

Additive, backward-compatible change: today `/chat` never times out on its own; after this change it does, bounded by a default that is more than double the worst latency observed in production load data so far. No data migration. Deploy is a normal code + config release:
1. Ship the code change with `CHAT_REQUEST_TIMEOUT_SECONDS` defaulting to `30` when unset, so no environment needs an explicit config change to pick up the new behavior.
2. If a deployed environment needs a different ceiling, set `CHAT_REQUEST_TIMEOUT_SECONDS` for that environment.

Rollback: revert the deploy. There is no persisted state introduced by this change (the new counter is in-memory, like the existing ones, and resets on process restart the same way).

## Open Questions

- **Frontend rendering of a 504.** Unresolved until the check task (see proposal `What Changes`) runs against the current `frontend/` code: does the existing non-200 handling path already produce an acceptable message, or does it need a fix? Scope is a check-and-fix, not a redesign, per the proposal's Non-Goals — but which of those two outcomes applies is not decided here.
- **Invalid `CHAT_REQUEST_TIMEOUT_SECONDS` values.** Not specified: should a non-numeric or non-positive value fail fast at process startup, or fall back silently to the default `30`? `DEPLOYMENT_ENVIRONMENT` (the precedent this variable's reading style follows) is a free-form string with no parsing failure mode, so it doesn't settle this by precedent. Left open for the tasks/implementation stage to decide, or to raise back to the user if it's judged to matter.
- **`except TimeoutError` catches more than this change's own deadline.** Since Python 3.10 `socket.timeout` is an alias of the builtin `TimeoutError`, and since 3.11 so are `asyncio.TimeoutError` and `concurrent.futures.TimeoutError`. A socket-level timeout raised anywhere inside the graph would therefore be caught by the `except TimeoutError` branch described in D2 and reported as a deadline expiry — a `504` plus a `chat_request_timeout_total` increment — even though the deadline had not elapsed. That corrupts the very counter this change adds. The probability is low (`google-genai` goes through `httpx`, whose timeouts are `httpx.TimeoutException` and are not in the `TimeoutError` hierarchy) but not zero. A cheap guard exists: the handler already captures `started = time.perf_counter()` at `backend/api/main.py:110`, so the branch can compare elapsed time against the configured deadline and re-raise if the deadline had not in fact been reached. Whether to add that guard or to accept the ambiguity is not decided here.
