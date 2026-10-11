"""
AegisAI Main Application Entrypoint.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.routing import Match

from app.api.router import api_router
from app.api.routes.websocket import router as websocket_router
from app.core.common.logging import logger, setup_logging
from app.core.config.settings import settings
from app.core.events.rabbitmq import close_rabbitmq
from app.core.metrics.prometheus import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    get_latest_metrics,
)
from app.core.middleware.error_handler import ErrorHandlerMiddleware
from app.core.middleware.rate_limiter import limiter
from app.database.init_db import init_db
from app.modules.simulation.scheduler import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the FastAPI application."""
    # Startup
    logger.info("aegis_backend_starting", title=settings.PROJECT_NAME, version=settings.VERSION)
    setup_logging()
    init_db()

    # Start background simulation scheduler
    setup_scheduler()

    yield

    # Shutdown
    logger.info("aegis_backend_shutting_down")
    shutdown_scheduler()
    await close_rabbitmq()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AegisAI - Production AI-Powered Emergency Response & Digital Twin Platform",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# SlowAPI Rate Limiter
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    return _rate_limit_exceeded_handler(request, exc)  # type: ignore[arg-type]


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


# Prometheus Telemetry Middleware
@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Record Prometheus metrics for non-metrics/health polling routes
    path = request.url.path
    if not path.startswith(("/metrics", "/api/v1/health")):
        handler = path
        for route in app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                handler = getattr(route, "path", path)
                break
        status_code = str(response.status_code)
        HTTP_REQUESTS_TOTAL.labels(method=request.method, handler=handler, status_code=status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=request.method, handler=handler).observe(duration)

    return response


# Global Error Handling Middleware
app.add_middleware(ErrorHandlerMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register WebSocket & REST API Routers
app.include_router(websocket_router)
app.include_router(api_router, prefix=settings.API_V1)


@app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
def metrics():
    """Prometheus exposition metrics endpoint."""
    data, content_type = get_latest_metrics()
    return Response(content=data, media_type=content_type)


@app.get("/", tags=["Health"])
def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "docs": "/docs",
    }
