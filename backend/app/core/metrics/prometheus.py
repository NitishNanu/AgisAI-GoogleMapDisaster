"""
AegisAI Core — Prometheus Metrics Exporter.

Exposes operational telemetry for Prometheus scraping at /metrics:
- HTTP request count and duration histogram
- Simulation engine ticks
- AI decision lifecycle events
- Emergency dispatches and allocations
"""


from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)

# Standard metrics
HTTP_REQUESTS_TOTAL = Counter(
    "aegis_http_requests_total",
    "Total HTTP requests handled by AegisAI backend",
    ["method", "handler", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "aegis_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "handler"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

SIMULATION_TICKS_TOTAL = Counter(
    "aegis_simulation_ticks_total",
    "Total simulation engine tick cycles executed",
)

AI_DECISIONS_TOTAL = Counter(
    "aegis_ai_decisions_total",
    "Total AI recommendations generated or transitioned",
    ["action", "status"],
)

DISPATCHES_TOTAL = Counter(
    "aegis_dispatches_total",
    "Total resource dispatch events executed",
    ["status"],
)


def get_latest_metrics() -> tuple[bytes, str]:
    """Generate Prometheus exposition format payload and content-type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
