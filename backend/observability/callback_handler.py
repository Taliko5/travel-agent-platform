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
"""

from collections import OrderedDict
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, set_span_in_context

tracer = trace.get_tracer(__name__)

# Cap on concurrently open spans per handler instance. Bounds memory when
# *_end/*_error callbacks don't fire (cancellation, disconnect, timeout).
_MAX_OPEN_SPANS = 1000


class OTelCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        # run_id -> open span, insertion-ordered so the oldest entry can be
        # evicted first. run_ids are unique per run, so a single shared
        # handler instance is safe across concurrent requests.
        self._spans: OrderedDict[UUID, Span] = OrderedDict()

    def _start_span(self, name: str, run_id: UUID, parent_run_id: UUID | None) -> None:
        if len(self._spans) >= _MAX_OPEN_SPANS:
            _, abandoned_span = self._spans.popitem(last=False)
            abandoned_span.set_status(
                Status(StatusCode.ERROR, "span abandoned: no matching end callback")
            )
            abandoned_span.end()
        parent_span = self._spans.get(parent_run_id) if parent_run_id else None
        context = set_span_in_context(parent_span) if parent_span else None
        span = tracer.start_span(name, context=context)
        # TODO: span naming/attributes not decided — tasks.md Section 9.
        self._spans[run_id] = span

    def _end_span(self, run_id: UUID, error: BaseException | None = None) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        if error is not None:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
        span.end()

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
        self._start_span(name, run_id, parent_run_id)

    def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_span(run_id)

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
        self._start_span(name, run_id, parent_run_id)

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._end_span(run_id)

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._end_span(run_id, error)

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
        self._start_span(name, run_id, parent_run_id)

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
