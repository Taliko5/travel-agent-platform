import logging
import os

import prometheus_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.graph import build_graph  # noqa: E402
from observability.callback_handler import OTelCallbackHandler  # noqa: E402
from observability.logging import configure_logging  # noqa: E402


resource = Resource.create(
    {
        "service.name": "travel-agent-backend",
        "service.version": "0.1.0",
        "deployment.environment": os.environ.get("DEPLOYMENT_ENVIRONMENT", "local"),
    }
)

tracer_provider = TracerProvider(resource=resource)
otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    )
else:
    # BatchSpanProcessor exports from a background thread, matching the OTLP
    # branch, so console export doesn't block the event loop on span end.
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

meter_provider = MeterProvider(
    resource=resource, metric_readers=[PrometheusMetricReader()]
)
set_meter_provider(meter_provider)

# Imported after set_meter_provider so the placeholder instruments register
# against the configured MeterProvider (exposed via /metrics).
from observability import metrics  # noqa: E402,F401

configure_logging()
logger = logging.getLogger(__name__)


app = FastAPI(title="travel agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Exclude self-observation noise: the compose healthcheck and Prometheus
# scrape hit these on a timer, generating spans even with zero user traffic.
FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
app.mount("/metrics", prometheus_client.make_asgi_app())
graph = build_graph()

# Registered once and reused: run_ids are unique per run, so a single shared
# handler is safe across concurrent /chat requests.
otel_callback_handler = OTelCallbackHandler()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    intent: str
    response: str


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
def root():
    return {"message": "travel agent API"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    logger.info("chat request received")
    result = await graph.ainvoke(
        {
            "user_input": request.message,
            "intent": None,
            "response": None,
            "flight_data": None,
            "weather_data": None,
            "hotel_data": None,
        },
        config={"callbacks": [otel_callback_handler]},
    )
    return ChatResponse(intent=result["intent"], response=result["response"])
