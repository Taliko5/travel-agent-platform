## Why

`POST /chat` awaits its graph invocation with nothing above it imposing a ceiling. During the 2026-08-12 load run, five consecutive requests each spent 34-35 seconds inside `google_genai`'s internal `tenacity` retry loop before it gave up. That bound came from the library's retry policy, not from `/chat`, and it applies to calls that *fail*. A call that hangs has no such bound, and nothing in the handler distinguishes the two cases.

**Correction to the original motivation.** This change was first written around a sixth request from that run, recorded at 1025.74 seconds and read as the same retry loop running unchecked for seventeen minutes. That reading was wrong: 999 of those seconds were a macOS Clamshell Sleep, and roughly 27 seconds of work took place. `docs/step8-host-network.md` records how that was established. The proposal no longer rests on that incident — the missing ceiling is a structural defect regardless of whether it has yet produced a dramatic one.

## What Changes

- Wrap the existing `await graph.ainvoke(...)` call in `backend/api/main.py`'s `/chat` handler with `asyncio.wait_for`, bounded by a configurable deadline.
- Add `CHAT_REQUEST_TIMEOUT_SECONDS` (default `30`), read the same way `DEPLOYMENT_ENVIRONMENT` is read at `backend/api/main.py:34`, and document it in `backend/.env.example`.
- On expiry, return `HTTP 504 Gateway Timeout` with a JSON `detail` body, instead of hanging indefinitely.
- Record the timeout as `status="error"` on the existing `chat_request_duration_seconds` histogram (no new label value), and add one new label-less counter, `chat_request_timeout_total`, seeded at 0 alongside the other counters in `seed_counters()`.
- Update the "four key Step 8 metrics" framing in `backend/observability/metrics.py`'s module docstring and in `docs/plan.md` to account for this fifth instrument.
- Check how the frontend renders a non-200 response from `/chat` today, and fix it if it renders badly.
- **BREAKING**: `/chat` can now return `504`. Any caller assuming it always eventually returns `200` or a fast client-side error will see a `504` on timeout.

## Capabilities

### New Capabilities
- `chat-api`: request-handling contract for the backend `POST /chat` endpoint — request/response shape, timeout behavior, and status semantics. Not previously specified; `chat-frontend` only specifies the frontend's side of this exchange.

### Modified Capabilities
(none — `chat-frontend`'s existing requirements around receiving a response or error from `/chat` are unaffected in their own terms; a 504 is still "an error" from that spec's perspective. If the frontend-rendering check in Impact below finds otherwise, `chat-frontend` may need a delta — flagged there, not assumed here.)

## Impact

- **Affected code**: `backend/api/main.py` (`/chat` handler), `backend/observability/metrics.py` (new counter, docstring), `backend/.env.example` (new variable), `docs/plan.md` (metric count framing).
- **Affected tests**: `backend/tests/` needs a case that makes the graph hang and asserts a `504` plus a `chat_request_timeout_total` increment; `test_observability.py`'s seeded-counter assertions need to cover the new counter.
- **CI**: `.github/workflows/ci.yml` runs the backend jobs only when `backend/**` changes; this change touches `backend/`, so CI will exercise it.
- **Frontend**: possibly `frontend/` if the non-200 rendering check in "What Changes" finds a gap — scope of that fix is a check-and-fix, not a redesign.
- **Coupling to note, not resolved here**: the 30s default is chosen partly because it lands on the `30.0` boundary in the bucket-boundary replacement set proposed at Section 9 of `openspec/changes/step8-observability-scaffold/tasks.md`. If either the deadline or that boundary set changes independently in the future, the other should be revisited.

## Non-Goals

- Fixing the host network failures that triggered the 2026-08-12 incident — tracked separately in `docs/step8-host-network.md`.
- Tuning `google_genai`'s retry/backoff policy.
- Per-node or per-LLM-call timeouts inside the graph.
- Classifying failure reasons other than timeout (e.g. distinguishing upstream 5xx from validation errors) — `status` stays exactly `ok` | `error`.
