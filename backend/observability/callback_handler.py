"""OpenTelemetry span instrumentation for LangGraph/LangChain runs.

`OTelCallbackHandler` is a `BaseCallbackHandler` translated LangChain callback
events into OTel spans. It is registered once via `config={"callbacks": [...]}`
where the graph is invoked in `backend/api/main.py`, so `backend/agent/graph.py`
and `backend/agent/nodes.py` need no changes.

Lifecycle: one span is opened per `run_id` on a `*_start` callback and closed on
the matching `*_end` (success) or `*_error` (failure) callback. End callbacks do
*not* reliably fire on client disconnect, timeout, or `asyncio.CancelledError`,
so `self._spans` is bounded: once it exceeds `_MAX_OPEN_SPANS`, the oldest
entry is evicted, marked as an abandoned span, and ended — reclaiming spans
that would otherwise accumulate unbounded for the lifetime of the shared
handler instance. Spans are nested by `parent_run_id`, so an LLM/tool span
opened inside a node appears under that node's span.

Span naming and attributes follow step8-metric-design design.md D9-D13 and
this repo's `LangGraph/LangChain Span Instrumentation via Callback Handler`
spec: span names are the static operation identifiers LangChain/LangGraph
already supply (never request/response data); node spans carry `intent` once
classify_intent has resolved one; the chat-model span carries OpenTelemetry's
GenAI attributes; no span carries free-text user input, model output, or any
other `AgentState` payload field.

`llm_call_duration_seconds` is recorded from `on_llm_end`/`on_llm_error`
(design.md D14/D15): its `node` label is the enclosing node's span name,
which `Span` — the OpenTelemetry *API* type this handler holds references to
— doesn't expose once created (that's an SDK-specific `ReadableSpan`
property). `_OpenSpan` carries the name and a start time alongside each span
for exactly this reason, rather than reaching into the SDK.
"""

import time
from collections import OrderedDict
from typing import Any, NamedTuple
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from observability.metrics import llm_call_duration
from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GenAiOperationNameValues,
    GenAiProviderNameValues,
)
from opentelemetry.trace import Span, Status, StatusCode, set_span_in_context

tracer = trace.get_tracer(__name__)

# Cap on concurrently open spans per handler instance. Bounds memory when
# *_end/*_error callbacks don't fire (cancellation, disconnect, timeout).
_MAX_OPEN_SPANS = 1000


class _OpenSpan(NamedTuple):
    name: str
    span: Span
    started: float
    parent_name: str | None


def _intent_attributes(data: Any) -> dict[str, Any]:
    """`intent`, if `data` (a node's inputs or outputs) has a resolved one.

    Bounded to `VALID_INTENTS` (design.md D13): a request-scoped value outside
    that set is never emitted, matching the `intent` metric label's own domain
    rather than computing it a second way.

    No `fallback` counterpart: it's a local in `classify_intent`, never
    returned in `AgentState` — see step8-metric-design design.md D10.
    """
    # Deferred import, matching observability/metrics.py: importing
    # agent.nodes at module level pulls observability.metrics in with it,
    # and that module must not execute before set_meter_provider() runs.
    from agent.nodes import VALID_INTENTS

    if isinstance(data, dict) and data.get("intent") in VALID_INTENTS:
        return {"intent": data["intent"]}
    return {}


def _genai_attributes(
    serialized: dict[str, Any] | None, kwargs: dict[str, Any]
) -> dict[str, Any]:
    """GenAI semantic-convention attributes for a chat-model call span."""
    invocation_params = kwargs.get("invocation_params") or {}
    model = invocation_params.get("model") or (serialized or {}).get("kwargs", {}).get(
        "model"
    )
    attributes: dict[str, Any] = {
        GEN_AI_PROVIDER_NAME: GenAiProviderNameValues.GCP_GEMINI.value,
        GEN_AI_OPERATION_NAME: GenAiOperationNameValues.GENERATE_CONTENT.value,
    }
    if model:
        attributes[GEN_AI_REQUEST_MODEL] = model
    return attributes


def _record_llm_call(entry: "_OpenSpan | None", status: str) -> None:
    """Record `llm_call_duration_seconds` for a just-ended LLM/chat-model span."""
    if entry is None:
        return
    duration = time.perf_counter() - entry.started
    # `node` is always present, falling back to "unknown" when the enclosing
    # node's span has been evicted: a series distinguishable only by a missing
    # label is the shape design.md D3/D17 refused for the counters.
    attributes: dict[str, Any] = {
        "status": status,
        "node": entry.parent_name or "unknown",
    }
    llm_call_duration.record(duration, attributes)


class OTelCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        # run_id -> open span, insertion-ordered so the oldest entry can be
        # evicted first. run_ids are unique per run, so a single shared
        # handler instance is safe across concurrent requests.
        self._spans: OrderedDict[UUID, _OpenSpan] = OrderedDict()

    def _start_span(
        self,
        name: str,
        run_id: UUID,
        parent_run_id: UUID | None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        if len(self._spans) >= _MAX_OPEN_SPANS:
            _, abandoned = self._spans.popitem(last=False)
            abandoned.span.set_status(
                Status(StatusCode.ERROR, "span abandoned: no matching end callback")
            )
            abandoned.span.end()
        parent = self._spans.get(parent_run_id) if parent_run_id else None
        context = set_span_in_context(parent.span) if parent else None
        span = tracer.start_span(name, context=context, attributes=attributes)
        parent_name = parent.name if parent else None
        self._spans[run_id] = _OpenSpan(name, span, time.perf_counter(), parent_name)

    def _end_span(
        self,
        run_id: UUID,
        error: BaseException | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> "_OpenSpan | None":
        entry = self._spans.pop(run_id, None)
        if entry is None:
            return None
        if attributes:
            entry.span.set_attributes(attributes)
        if error is not None:
            entry.span.record_exception(error)
            entry.span.set_status(Status(StatusCode.ERROR, str(error)))
        entry.span.end()
        return entry

    # --- Chain (LangGraph node) events -----------------------------------
    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = kwargs.get("name") or (serialized or {}).get("name") or "chain"
        self._start_span(name, run_id, parent_run_id, _intent_attributes(inputs))

    def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_span(run_id, attributes=_intent_attributes(outputs))

    def on_chain_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._end_span(run_id, error)

    # --- LLM events ------------------------------------------------------
    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = kwargs.get("name") or (serialized or {}).get("name") or "llm"
        self._start_span(
            name, run_id, parent_run_id, _genai_attributes(serialized, kwargs)
        )

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        _record_llm_call(self._end_span(run_id), "ok")

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        _record_llm_call(self._end_span(run_id, error), "error")

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        # Chat models (e.g. ChatGoogleGenerativeAI) fire this instead of
        # on_llm_start. No separate end-side method is needed: on_llm_end /
        # on_llm_error already terminate chat model spans too.
        name = kwargs.get("name") or (serialized or {}).get("name") or "llm"
        self._start_span(
            name, run_id, parent_run_id, _genai_attributes(serialized, kwargs)
        )

    # --- Tool events -----------------------------------------------------
    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = kwargs.get("name") or (serialized or {}).get("name") or "tool"
        self._start_span(name, run_id, parent_run_id)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_span(run_id)

    def on_tool_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._end_span(run_id, error)
