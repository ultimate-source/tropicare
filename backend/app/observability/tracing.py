# ─────────────────────────────────────────────────────────────────────────────
# backend/app/observability/tracing.py — OpenTelemetry tracing configuration
# ─────────────────────────────────────────────────────────────────────────────
"""
Configures the OpenTelemetry SDK to export traces to Jaeger via OTLP gRPC.
Call ``init_tracing()`` once at application startup (gateway lifespan).

Child spans are created automatically by:
  - ``opentelemetry-instrumentation-fastapi`` for HTTP requests
  - ``BaseAgent.run()`` for each agent execution
  - ``MCPClient.call()`` for each MCP tool invocation
"""
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing(
    service_name: str = "tropicare-gateway",
    otlp_endpoint: str | None = None,
) -> TracerProvider:
    """Bootstrap the OTel tracer provider and register it globally.

    Parameters
    ----------
    service_name:
        Logical service name that appears in Jaeger.
    otlp_endpoint:
        OTLP gRPC collector endpoint.  Defaults to ``OTEL_EXPORTER_OTLP_ENDPOINT``
        env var or ``http://localhost:4317``.
    """
    endpoint = otlp_endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
    )

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return provider
