import logging

from opentelemetry import trace
from pythonjsonlogger.json import JsonFormatter


class TraceCorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            record.trace_id = format(span_context.trace_id, "032x")
            record.span_id = format(span_context.span_id, "016x")
        else:
            record.trace_id = None
            record.span_id = None
        return True


def build_json_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.addFilter(TraceCorrelationFilter())
    return handler


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers = [build_json_handler()]
    root_logger.setLevel(logging.INFO)
