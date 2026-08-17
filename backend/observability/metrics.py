"""Placeholder OpenTelemetry metric instruments for the four key Step 8 metrics.

The instruments named in `docs/plan.md` (`/chat` latency, intent distribution,
LLM call duration, RAG retrieval rate) are *declared* here so recording call
sites have a single, consistent home to import from. No data is recorded yet:
label sets, histogram bucket boundaries, and the actual `.record()`/`.add()`
calls are the user's metric-design work. See `docs/step8.md` for the
scaffolded-vs-yours split.

`seed_counters()` must be called from `backend/api/main.py` after the
`MeterProvider` is configured (`set_meter_provider(meter_provider)`) so the
seeded measurements register against it and are exposed via `/metrics`.
Measurements recorded before a provider is installed are OTel proxy
instrument no-ops and are silently dropped.
"""

from opentelemetry import metrics

meter = metrics.get_meter("travel-agent-backend")

# /chat request latency.
# Recorded in the POST /chat route handler in backend/api/main.py, in a
# `finally` block so failed requests are measured too.
# Labels: intent (4 values + "unknown"), status (ok|error) — 10 series max.
# Bucket boundaries are provisional starting values; tune them once real
# latency data has accumulated.
chat_request_duration = meter.create_histogram(
    name="chat_request_duration_seconds",
    unit="s",
    description="End-to-end latency of POST /chat requests.",
    explicit_bucket_boundaries_advisory=[
        0.5,
        1.0,
        1.5,
        2.0,
        3.0,
        5.0,
        7.0,
        10.0,
        20.0,
        60.0,
        120.0,
    ],
)

# Classifier health, not intent distribution.
# Recorded in classify_intent in backend/agent/nodes.py.
# Labels: intent, fallback (true|false).
# Intent *distribution* is already available from
# chat_request_duration_seconds_count{intent=...}; what this counter adds is
# the `fallback` dimension — how often the LLM returned something outside the
# allowlist and got silently coerced to "general". That signal is invisible in
# the resolved-intent label, and without it a rising "general" share can't be
# told apart from a degrading classifier.
intent_classification_count = meter.create_counter(
    name="intent_classification_total",
    unit="1",
    description="Count of requests by classified intent.",
)

# LLM call duration.
# TODO (user): define labels and add .record() calls where get_model().invoke
# is called in classify_intent / generate_response in backend/agent/nodes.py
# (or record from OTelCallbackHandler on_llm_start/on_llm_end). Bucket
# boundaries below are provisional starting values, not a final decision.
llm_call_duration = meter.create_histogram(
    name="llm_call_duration_seconds",
    unit="s",
    description="Duration of individual LLM (Gemini) calls.",
    explicit_bucket_boundaries_advisory=[
        0.5,
        1.0,
        1.5,
        2.0,
        3.0,
        5.0,
        7.0,
        10.0,
        20.0,
        60.0,
        120.0,
    ],
)

# RAG retrieval rate.
# TODO (user): define labels/buckets and add .add() calls in retrieve_context_node
# in backend/agent/nodes.py (or in rag/retriever.retrieve_context).
rag_retrieval_count = meter.create_counter(
    name="rag_retrieval_total",
    unit="1",
    description="Count of RAG context retrievals.",
)


def seed_counters() -> None:
    """Seed counters so they're visible on /metrics before any real traffic.

    OTel's PrometheusMetricReader only exports an instrument once it has at
    least one data point. Counters starting at 0 are a truthful
    representation, so we seed them to make them visible on /metrics
    immediately. Histograms are deliberately *not* seeded: a fake
    `.record(0)` would inject a permanent "one observation of 0 seconds"
    data point that skews histogram_quantile() and rate(_sum)/rate(_count)
    (average latency) from the very first scrape. The two histograms simply
    won't appear on /metrics until real recording is wired in — see the
    TODOs above.

    Must be called after `set_meter_provider()` is installed (see
    `backend/api/main.py`) — these instruments are OTel proxies until then,
    and measurements recorded on a proxy before a provider is installed are
    dropped silently.
    """
    # Deferred import: agent.nodes imports intent_classification_count from
    # this module, so importing VALID_INTENTS at module level would be
    # circular.
    from agent.nodes import VALID_INTENTS

    for intent in VALID_INTENTS:
        for fallback in ("true", "false"):
            intent_classification_count.add(0, {"intent": intent, "fallback": fallback})
    rag_retrieval_count.add(0)
