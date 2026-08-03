# Step 8 Fixes (instructions for Claude Code)

Fixes for defects found while reviewing the observability code added in Step 8
(`openspec/changes/step8-observability-scaffold/`).
Implement **these 6 items only**. Do not make improvements or refactors that aren't listed here.

## Ground rules

- Files in scope: `backend/observability/metrics.py`, `backend/observability/callback_handler.py`, `backend/api/main.py`, `backend/tests/test_observability.py`
- **Do not touch**: `backend/agent/graph.py`, `backend/agent/nodes.py`, `backend/rag/`, `frontend/`, `.github/workflows/ci.yml`, `docker-compose.yaml`
- Preserve Step 8's design intent:
  - Actual metric recording (the `.record()` / `.add()` call sites) is **the user's work** — do not implement it. Keep the `# TODO (user)` comments.
  - Span attribute design (intent, model name, etc.) is also **the user's work**. Keep those `# TODO (user)` comments.
  - Keep registering `OTelCallbackHandler` once at graph-invocation time. Do not convert it into per-node decorators.
- Do not change dependency versions (`opentelemetry-*` at 1.43.0 / 0.64b0, `langchain-core==1.4.8`)
- When done, `cd backend && pytest tests/ -v`, `ruff check backend/`, and `ruff format --check backend/` must all pass
- Finally, update any statements in `docs/step8.md` that no longer match the post-fix behavior

---

## Fix 1: Remove the `record(0)` seed on the histograms

**File**: `backend/observability/metrics.py`

**Current state**: all four instruments get a zero-value seed at the end of the file.

```python
chat_request_duration.record(0)
intent_classification_count.add(0)
llm_call_duration.record(0)
rag_retrieval_count.add(0)
```

**Problem**: `add(0)` on a counter is the standard Prometheus idiom, but `record(0)` on a histogram permanently injects a fake data point meaning "one observation of 0 seconds latency". Inspecting the actual `/metrics` output confirms:

```
chat_request_duration_seconds_bucket{le="0.0",...} 1.0
chat_request_duration_seconds_count{...} 1.0
chat_request_duration_seconds_sum{...} 0.0
```

This skews `histogram_quantile()` and `rate(_sum)/rate(_count)` (average latency) from the very first scrape.

**Approach**:
- **Delete** `.record(0)` for both histograms (`chat_request_duration`, `llm_call_duration`)
- **Keep** `.add(0)` for both counters (`intent_classification_count`, `rag_retrieval_count`) — a counter starting at 0 is a truthful representation and does no harm
- Rewrite the trailing comment so it explains why only counters are seeded, and why it is correct for the histograms not to appear on `/metrics` until real recording is wired in

**Acceptance criteria**:
- `chat_request_duration_seconds` and `llm_call_duration_seconds` do **not** appear in `/metrics` output (until real recording is added)
- `intent_classification_total` and `rag_retrieval_total` still appear with value `0.0`
- Fix 6 updates the tests to match these new expectations

---

## Fix 2: Set explicit histogram bucket boundaries

**File**: `backend/observability/metrics.py`

**Problem**: the OTel SDK's default bucket boundaries are `0, 5, 10, 25, 50, 75, 100, 250, 500, 750, 1000, 2500, 5000, 7500, 10000` — values designed for **milliseconds**. Both histograms declare `unit="s"`, so real `/chat` latencies (roughly 1–5s) and LLM call durations (roughly 1–3s) all land in the first two buckets, making percentiles uncomputable.

`docs/step8.md` says bucket design is the user's work, but it does not say that **the default is unusable at second granularity** — using it as-is is simply broken.

**Approach**:
- Pass `explicit_bucket_boundaries_advisory` to `create_histogram()` (available as a keyword-only argument in `opentelemetry-api==1.43.0`; verified working)
- Use sensible second-scale starting values, e.g.:
  - `chat_request_duration`: `[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]`
  - `llm_call_duration`: `[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]`
- Add a comment making clear these are **reasonable starting values, not a final decision**, and that bucket tuning remains part of the existing `# TODO (user)`

**Acceptance criteria**:
- A manual `.record(1.3)` lands with `le="1"` at 0 and `le="2"` at 1 (boundaries are in effect)
- The `# TODO (user)` comments are still present

---

## Fix 3: Close the span leak in `OTelCallbackHandler`

**File**: `backend/observability/callback_handler.py`

**Current state**: the module docstring claims:

> LangChain guarantees exactly one `_end`/`_error` fires per `_start`, so spans don't leak on error.

**Problem**: this claim is false. On client disconnect, timeout, or cancellation via `asyncio.CancelledError`, neither `on_*_end` nor `on_*_error` fires. `OTelCallbackHandler` is instantiated once at module load in `api/main.py` and shared for the process lifetime, so `self._spans` accumulates unterminated `Span` objects without bound (a memory leak). Those spans are never `end()`ed, so they are never exported either.

**Approach** (pick one; the first is preferred):

- **Option A (preferred)**: bound `self._spans`. Use `collections.OrderedDict`; when the entry count exceeds a cap (e.g. 1000), evict the oldest entry, set `Status(StatusCode.ERROR, "span abandoned: no matching end callback")` on it, `end()` it, then discard. Extract the cap as a named constant with a comment.
- **Option B**: store an insertion timestamp alongside each span and sweep entries older than a threshold (e.g. 5 minutes) on each `_start_span`.

Either way:
- Remove the incorrect "spans don't leak" assertion from the docstring and replace it with an explanation that end callbacks do not fire on cancellation, so the handler reclaims abandoned spans
- Do not change the signatures of `_start_span` / `_end_span` (they are called from the `on_*` methods and from tests)

**Acceptance criteria**:
- Calling `on_chain_start` past the cap leaves `self._spans` capped in size
- Evicted spans have been `end()`ed with `ERROR` status (verified by a test in Fix 6)

---

## Fix 4: Implement `on_chat_model_start` explicitly

**File**: `backend/observability/callback_handler.py`

**Problem**: `ChatGoogleGenerativeAI` is a chat model, so LangChain fires `on_chat_model_start`, not `on_llm_start`. Because it isn't implemented, this currently works only by accident: `_achat_model_start_fallback` in `langchain_core/callbacks/manager.py` catches the `NotImplementedError` from `BaseCallbackHandler.on_chat_model_start` and falls back to `on_llm_start`.

Consequences:
- An exception is raised and caught on every single LLM call
- On the fallback path `messages` is flattened via `get_buffer_string()`, losing the message structure (which will be needed later for span attributes)
- The behavior depends on a langchain-core implementation detail and could break on upgrade

**Approach**:
- Implement `on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs)`. Note that `messages` is `list[list[BaseMessage]]`
- The body just calls `self._start_span(name, run_id, parent_run_id)`, same as `on_llm_start`
- Resolve the span name with the same logic as the other three (`kwargs.get("name") or (serialized or {}).get("name") or ...`)
- Do **not** add a new end-side method — the existing `on_llm_end` / `on_llm_error` already handle termination for chat models too. Note this in a comment
- Place it under the existing `# --- LLM events ---` section

**Acceptance criteria**:
- An `on_chat_model_start` → `on_llm_end` pair opens and closes a span correctly
- The langchain-core fallback path is no longer exercised

---

## Fix 5: Exclude `/health` and `/metrics` from tracing, and make console export async

**File**: `backend/api/main.py`

**Problem 5-1**: `FastAPIInstrumentor.instrument_app(app)` is called without `excluded_urls`. The docker-compose healthcheck (every 30s) and the Prometheus scrape (every 15s) generate spans forever, even with zero user traffic.

**Problem 5-2**: when no OTLP endpoint is configured, the code uses `SimpleSpanProcessor(ConsoleSpanExporter())`. `SimpleSpanProcessor` writes to stdout synchronously on span end, blocking the event loop on the request path. Combined with 5-1, this means periodic stdout writes even when idle.

**Approach**:
- Pass `excluded_urls="health,metrics"` to `instrument_app` (the `excluded_urls: str | None` parameter is confirmed to exist)
- Switch the console branch to `BatchSpanProcessor(ConsoleSpanExporter())` so it matches the OTLP branch and moves writes to a background thread
- Add a one-line comment explaining the exclusion (avoiding self-observation noise)

**Acceptance criteria**:
- No FastAPI spans are produced for `GET /health` or `GET /metrics/`
- `POST /chat` spans are produced as before
- The existing `backend/tests/test_api_main.py` passes **unmodified**

---

## Fix 6: Rewrite `test_observability.py` so it actually tests something

**File**: `backend/tests/test_observability.py`

**Problem**: every current case only asserts `run_id not in handler._spans` — membership in a private dict. All tests would still pass if `_end_span` popped the entry without calling `span.end()`. Worst of all, `test_nested_span_parented_correctly` asserts nothing about parenting; it passes even if `_start_span` ignores `parent_run_id` entirely. The test name does not match what it verifies.

**Approach**:

1. **Add a fixture based on `InMemorySpanExporter`**
   - Build an isolated `TracerProvider` from `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter` plus `SimpleSpanProcessor`, and swap the `callback_handler` module's `tracer` to it (`monkeypatch.setattr("observability.callback_handler.tracer", ...)`). Do not mutate the global `TracerProvider` — that would pollute the setup in `api.main`
   - Clear the exporter after each test

2. **Stop poking at the private `handler._spans`; assert on exported spans instead**
   - Success path: exactly one span is exported, `span.name` matches expectations, and `span.status.status_code` is not `ERROR`
   - Failure path: the span is exported with `span.status.status_code == StatusCode.ERROR` and an exception event recorded
   - Cover all three families: chain / llm / tool

3. **Make `test_nested_span_parented_correctly` actually verify parenting**
   - Open and close a parent chain span and a child llm span, then assert the child's `span.parent.span_id` equals the parent's `span.get_span_context().span_id`
   - This is the only assertion that matches what the test name claims

4. **Add a test for Fix 4**
   - Verify `on_chat_model_start` → `on_llm_end` opens and closes a span
   - Pass `messages` as `list[list[BaseMessage]]`, e.g. `[[HumanMessage(content="hi")]]`

5. **Add a test for Fix 3**
   - Call `on_chain_start` more times than the cap without ever ending them; assert `handler._spans` stays capped and that evicted spans were exported as `end()`ed with `StatusCode.ERROR`
   - This test may read `_spans` since it needs the cap, but import the constant from the module rather than hardcoding a magic number

6. **Align the `/metrics` test with Fix 1 and Fix 5**
   - Use `/metrics/` (with the trailing slash). `app.mount("/metrics", ...)` returns a 307 redirect without it, so the current test only passes because `TestClient` follows redirects by default — it verifies nothing
   - Add one test that explicitly asserts, with `follow_redirects=False`, that `GET /metrics` is 307 and `GET /metrics/` is 200
   - Change the body assertions to the two seeded counters (`intent_classification_total`, `rag_retrieval_total`). Assert the two histograms are **absent** per Fix 1, and comment on why

7. **Add tests for `TraceCorrelationFilter`** (`backend/observability/logging.py`)
   - With an active span, a log record gets a 32-hex-digit `trace_id` and a 16-hex-digit `span_id`
   - With no active span, both are `None` and nothing raises
   - The rendered JSON output actually contains the `trace_id` / `span_id` keys (`python-json-logger==4.1.0` does include filter-attached attributes in its output; verified)

**Acceptance criteria**:
- Deleting `span.end()` from `_end_span` makes at least one test fail (i.e. the tests have teeth)
- Removing `parent_run_id` handling from `_start_span` makes `test_nested_span_parented_correctly` fail
- Running the tests does not flood stdout with console-exporter span JSON
- The full suite passes without `GOOGLE_API_KEY` (preserving the pre-Step-8 invariant)

---

## Wrap-up

1. Run `cd backend && pytest tests/ -v` and confirm everything passes
2. Run `ruff check backend/` and `ruff format --check backend/`
3. Update `docs/step8.md` to match the post-fix reality. At minimum these statements go stale:
   - "the four placeholder instruments will show `0` on `/metrics`" → now only the two counters (Fix 1)
   - The console exporter being a `SimpleSpanProcessor` (Fix 5)
   - Add a note that `/health` and `/metrics` are excluded from tracing (Fix 5)
   - Reflect in "Scaffolded vs. Yours" that starting bucket boundaries are now set, and that they are provisional (Fix 2)
4. Present a summary of the changes. Do not commit.
