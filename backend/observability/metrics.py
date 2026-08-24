"""OpenTelemetry metric instruments for the four key Step 8 metrics.

All four are declared here so recording call sites have a single, consistent
home to import from, and all four are recorded: `chat_request_duration` and
`intent_classification_count` from `backend/api/main.py`/`backend/agent/nodes.py`,
`llm_call_duration` from `backend/observability/callback_handler.py`
(step8-metric-design design.md D14/D15), and `rag_retrieval_count` from
`backend/agent/nodes.py`'s `retrieve_context_node` (design.md D17). Label sets
and bucket boundaries are this change's metric-design work; see `docs/step8.md`
for the scaffolded-vs-designed split.

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
# Boundaries: agreed replacement from the 2026-08-11 measurement, tasks.md
# Section 1 ("Re-tune chat_request_duration_seconds bucket boundaries") —
# not the scaffold's original guess. Retains 0.5/1.0/2.0 for the still-empty
# error path; 5.0-10.0 at 1s steps, where 121 of 127 observed requests
# landed; 12/15/20 subdividing the weather tail.
chat_request_duration = meter.create_histogram(
    name="chat_request_duration_seconds",
    unit="s",
    description="End-to-end latency of POST /chat requests.",
    explicit_bucket_boundaries_advisory=[
        0.5,
        1.0,
        2.0,
        5.0,
        6.0,
        7.0,
        8.0,
        9.0,
        10.0,
        12.0,
        15.0,
        20.0,
        30.0,
        60.0,
    ],
)

# Classifier health, not intent distribution — fallback-dimension rationale in
# docs/step8-task9c9d.md panels 3 & 5. Labels: intent, fallback (true|false).
intent_classification_count = meter.create_counter(
    name="intent_classification_total",
    unit="1",
    description="Count of requests by classified intent.",
)

# LLM call duration.
# Recorded in OTelCallbackHandler.on_llm_end/on_llm_error — see design.md D14.
# Labels: node (classify_intent|call_weather_tool|generate_response, or
# unknown if the enclosing span was evicted), status (ok|error) — 8 series max.
# Boundaries: the one measured re-tune D5 allows, spent on the 2026-08-22
# 17:57:53-18:10:15 run, tasks.md Section 1 / design.md D18 — not the D16
# coarse starting set. classify_intent/call_weather_tool's fast tail sits in
# 0.5-2.0s with no observation ever below 0.5; generate_response's calls sit
# in 3.0-7.0s. 1.5 splits the former without direct sub-bucket evidence (D18
# says so explicitly); 4.0/6.0 split the latter at the same 1s floor
# chat_request_duration_seconds's own re-tune used, one layer down. These
# boundaries hold no data until traffic next runs — see D18's last paragraph.
# 30.0 is the empty-but-deliberate tail marker: without it a slow-failing call
# reports only +Inf. Same reasoning as chat_request_duration_seconds's 12-60.
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
        4.0,
        5.0,
        6.0,
        7.0,
        10.0,
        30.0,
    ],
)

# RAG retrieval rate.
# Recorded in agent/nodes.py's retrieve_context_node — see design.md D17.
# Labels: intent (VALID_INTENTS) — 4 series max. Recorded unconditionally
# (attempt semantics), so no status label.
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
    (average latency) from the very first scrape. Both histograms simply
    won't appear on /metrics until real recording occurs.

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
    # Labelled, not bare — design.md D17 supersedes the original bare
    # .add(0): a label-less seed left in place alongside a labelled
    # recording site would produce an intent="" series alongside the real
    # ones, the exact pollution D3 refused for intent_classification_total.
    for intent in VALID_INTENTS:
        rag_retrieval_count.add(0, {"intent": intent})
