"""OpenTelemetry span instrumentation for LangGraph/LangChain runs.

`OTelCallbackHandler` is a `BaseCallbackHandler` translated LangChain callback
events into OTel spans. It is registered once via `config={"callbacks": [...]}`
where the graph is invoked in `backend/api/main.py`, so `backend/agent/graph.py`
and `backend/agent/nodes.py` need no changes.

Lifecycle: one span is opened per `run_id` on a `*_start` callback and closed on
the matching `*_end` (success) or `*_error` (failure) callback. LangChain
guarantees exactly one `_end`/`_error` fires per `_start`, so spans don't leak on
error. Spans are nested by `parent_run_id`, so an LLM/tool span opened inside a
node appears under that node's span.
"""

from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, set_span_in_context

tracer = trace.get_tracer(__name__)


class OTelCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        # run_id -> open span. run_ids are unique per run, so a single shared
        # handler instance is safe across concurrent requests.
        self._spans: dict[UUID, Span] = {}

    def _start_span(
        self, name: str, run_id: UUID, parent_run_id: UUID | None
    ) -> None:
        parent_span = self._spans.get(parent_run_id) if parent_run_id else None
        context = set_span_in_context(parent_span) if parent_span else None
        span = tracer.start_span(name, context=context)
        # TODO (user): set real span attributes here (e.g. intent, model name,
        # prompt/response sizes, tool args). The scaffold intentionally leaves
        # span naming/attribute design to your metric/trace pass.
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
