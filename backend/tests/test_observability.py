"""
Unit tests for backend/observability/ — the /metrics endpoint and
OTelCallbackHandler span lifecycle.

Mirrors test_api_main.py's approach for the /metrics tests: mocked graph,
real TestClient. OTelCallbackHandler tests swap `callback_handler.tracer` for
an isolated TracerProvider backed by InMemorySpanExporter so assertions can
be made on actually-exported spans, rather than on the handler's private
`_spans` dict.
"""

import io
import json
import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode
from pythonjsonlogger.json import JsonFormatter

import observability.callback_handler as callback_handler_module
from observability.callback_handler import _MAX_OPEN_SPANS, OTelCallbackHandler
from observability.logging import TraceCorrelationFilter


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app)


@pytest.fixture
def span_exporter(monkeypatch):
    """Isolated tracer wired to an in-memory exporter.

    Swaps only `observability.callback_handler.tracer` — the global
    TracerProvider set up in api.main is left untouched.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        callback_handler_module, "tracer", provider.get_tracer(__name__)
    )
    yield exporter
    exporter.clear()


@pytest.fixture
def handler():
    return OTelCallbackHandler()


class TestMetricsEndpoint:
    def test_metrics_trailing_slash_redirect(self, client):
        # app.mount("/metrics", ...) 307-redirects the bare path; TestClient
        # follows redirects by default, so this must disable that to mean
        # anything.
        response = client.get("/metrics", follow_redirects=False)
        assert response.status_code == 307

        response = client.get("/metrics/", follow_redirects=False)
        assert response.status_code == 200

    def test_metrics_body_has_seeded_counters_not_histograms(self, client):
        response = client.get("/metrics/")

        assert response.status_code == 200
        body = response.text
        assert "intent_classification_total" in body
        assert "rag_retrieval_total" in body
        # Histograms are intentionally unseeded (Fix 1): the OTel Prometheus
        # reader only exports an instrument once it has a data point, and no
        # real .record() call sites exist yet.
        assert "chat_request_duration_seconds" not in body
        assert "llm_call_duration_seconds" not in body


class TestChainSpans:
    def test_chain_success_exports_ok_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_chain_start({"name": "classify_intent"}, {}, run_id=run_id)
        handler.on_chain_end({}, run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "classify_intent"
        assert spans[0].status.status_code != StatusCode.ERROR

    def test_chain_error_exports_error_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_chain_start({"name": "classify_intent"}, {}, run_id=run_id)
        handler.on_chain_error(ValueError("boom"), run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR
        assert len(spans[0].events) == 1
        assert spans[0].events[0].name == "exception"


class TestLLMSpans:
    def test_llm_success_exports_ok_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_llm_start({"name": "gemini"}, ["prompt"], run_id=run_id)
        handler.on_llm_end(object(), run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "gemini"
        assert spans[0].status.status_code != StatusCode.ERROR

    def test_llm_error_exports_error_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_llm_start({"name": "gemini"}, ["prompt"], run_id=run_id)
        handler.on_llm_error(RuntimeError("llm failed"), run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR
        assert len(spans[0].events) == 1
        assert spans[0].events[0].name == "exception"

    def test_on_chat_model_start_opens_and_closes_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_chat_model_start(
            {"name": "gemini"},
            [[HumanMessage(content="hi")]],
            run_id=run_id,
        )
        handler.on_llm_end(object(), run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "gemini"
        assert spans[0].status.status_code != StatusCode.ERROR


class TestToolSpans:
    def test_tool_success_exports_ok_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_tool_start({"name": "search_flights"}, "query", run_id=run_id)
        handler.on_tool_end("result", run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "search_flights"
        assert spans[0].status.status_code != StatusCode.ERROR

    def test_tool_error_exports_error_span(self, span_exporter, handler):
        run_id = uuid4()

        handler.on_tool_start({"name": "search_flights"}, "query", run_id=run_id)
        handler.on_tool_error(RuntimeError("tool failed"), run_id=run_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR
        assert len(spans[0].events) == 1
        assert spans[0].events[0].name == "exception"


class TestSpanParenting:
    def test_nested_span_parented_correctly(self, span_exporter, handler):
        parent_id = uuid4()
        child_id = uuid4()

        handler.on_chain_start({"name": "generate_response"}, {}, run_id=parent_id)
        handler.on_llm_start(
            {"name": "gemini"}, ["prompt"], run_id=child_id, parent_run_id=parent_id
        )
        handler.on_llm_end(object(), run_id=child_id)
        handler.on_chain_end({}, run_id=parent_id)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 2

        parent_span = next(s for s in spans if s.name == "generate_response")
        child_span = next(s for s in spans if s.name == "gemini")

        assert child_span.parent is not None
        assert child_span.parent.span_id == parent_span.get_span_context().span_id


class TestSpanCapEviction:
    def test_eviction_caps_open_spans_and_ends_abandoned_with_error(
        self, span_exporter, handler
    ):
        overflow = 5
        for _ in range(_MAX_OPEN_SPANS + overflow):
            handler.on_chain_start({"name": "node"}, {}, run_id=uuid4())

        assert len(handler._spans) == _MAX_OPEN_SPANS

        evicted = span_exporter.get_finished_spans()
        assert len(evicted) == overflow
        assert all(s.status.status_code == StatusCode.ERROR for s in evicted)


class TestTraceCorrelationFilter:
    def test_attaches_ids_when_span_active(self):
        provider = TracerProvider()
        tracer = provider.get_tracer(__name__)
        filter_ = TraceCorrelationFilter()
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)

        with tracer.start_as_current_span("test-span"):
            filter_.filter(record)

        assert record.trace_id is not None
        assert len(record.trace_id) == 32
        int(record.trace_id, 16)  # raises if not valid hex

        assert record.span_id is not None
        assert len(record.span_id) == 16
        int(record.span_id, 16)  # raises if not valid hex

    def test_none_when_no_active_span(self):
        filter_ = TraceCorrelationFilter()
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)

        result = filter_.filter(record)

        assert result is True
        assert record.trace_id is None
        assert record.span_id is None

    def test_json_output_contains_trace_and_span_id(self):
        stream = io.StringIO()
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(
            JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        stream_handler.addFilter(TraceCorrelationFilter())

        logger = logging.getLogger("test_observability_trace_correlation")
        logger.handlers = [stream_handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        provider = TracerProvider()
        tracer = provider.get_tracer(__name__)
        with tracer.start_as_current_span("test-span"):
            logger.info("hello")

        output = json.loads(stream.getvalue())
        assert "trace_id" in output
        assert "span_id" in output
