"""Placeholder OpenTelemetry metric instruments for the four key Step 8 metrics.

The instruments named in `docs/plan.md` (`/chat` latency, intent distribution,
LLM call duration, RAG retrieval rate) are *declared* here so recording call
sites have a single, consistent home to import from. No data is recorded yet:
label sets, histogram bucket boundaries, and the actual `.record()`/`.add()`
calls are the user's metric-design work. See `docs/step8.md` for the
scaffolded-vs-yours split.

Imported from `backend/api/main.py` after the `MeterProvider` is configured so
these instruments register against it and are exposed via `/metrics`.
"""

from opentelemetry import metrics

meter = metrics.get_meter("travel-agent-backend")

# /chat request latency.
# TODO (user): define labels/buckets and add .record() calls in the POST /chat
# route handler in backend/api/main.py (wrap the graph.ainvoke call).
chat_request_duration = meter.create_histogram(
    name="chat_request_duration_seconds",
    unit="s",
    description="End-to-end latency of POST /chat requests.",
)

# Classified intent distribution.
# TODO (user): define labels/buckets and add .add() calls in classify_intent in
# backend/agent/nodes.py, labelled by the resolved intent.
intent_classification_count = meter.create_counter(
    name="intent_classification_total",
    unit="1",
    description="Count of requests by classified intent.",
)

# LLM call duration.
# TODO (user): define labels/buckets and add .record() calls where
# get_model().invoke is called in classify_intent / generate_response in
# backend/agent/nodes.py (or record from OTelCallbackHandler on_llm_start/on_llm_end).
llm_call_duration = meter.create_histogram(
    name="llm_call_duration_seconds",
    unit="s",
    description="Duration of individual LLM (Gemini) calls.",
)

# RAG retrieval rate.
# TODO (user): define labels/buckets and add .add() calls in retrieve_context_node
# in backend/agent/nodes.py (or in rag/retriever.retrieve_context).
rag_retrieval_count = meter.create_counter(
    name="rag_retrieval_total",
    unit="1",
    description="Count of RAG context retrievals.",
)
