"""OpenTelemetry tracer configuration."""

from __future__ import annotations

from stocktrace.infrastructure.config import ObservabilitySettings


def configure_tracing(settings: ObservabilitySettings) -> None:
    """Set up OpenTelemetry TracerProvider if OTEL is enabled.

    This function is a no-op when ``otel_enabled=False`` so the application starts
    cleanly without the OTEL SDK installed.  When enabled, it configures:
      - OTLP gRPC exporter (pointing at ``otel_endpoint``)
      - BatchSpanProcessor for low-overhead export
      - Auto-instrumentation hooks for FastAPI, httpx, asyncpg, and redis
    """
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace  # noqa: PLC0415
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # noqa: PLC0415
        from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        msg = (
            "opentelemetry-sdk and opentelemetry-exporter-otlp-proto-grpc are required "
            "when observability.otel_enabled=true. "
            "Install them with: pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc"
        )
        raise RuntimeError(msg) from exc

    resource = Resource.create({"service.name": settings.otel_service_name})
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _instrument_libraries()


def _instrument_libraries() -> None:
    """Apply OTEL auto-instrumentation for common libraries."""
    _try_instrument("opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor", lambda cls: cls().instrument())
    _try_instrument("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor", lambda cls: cls().instrument())
    _try_instrument("opentelemetry.instrumentation.asyncpg", "AsyncPGInstrumentor", lambda cls: cls().instrument())
    _try_instrument("opentelemetry.instrumentation.redis", "RedisInstrumentor", lambda cls: cls().instrument())


def _try_instrument(module_path: str, class_name: str, fn: object) -> None:
    """Attempt to instrument a library — silently skip if package is missing."""
    import importlib  # noqa: PLC0415

    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        fn(cls)  # type: ignore[operator]
    except (ImportError, Exception):  # noqa: BLE001
        pass  # Optional instrumentation — never block startup
