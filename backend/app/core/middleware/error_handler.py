"""
AegisAI Global Error Handling Middleware.

Intercepts all exceptions at the ASGI boundary and serializes them into
the standardized ApiResponse error format. Also injects request timing
information via the X-Process-Time-Ms response header.

Handled exception types:
  1. AegisException subclasses — domain errors with known HTTP status codes
  2. RequestValidationError — Pydantic validation failures (422)
  3. Exception — unhandled system errors (500)
"""

import time
import uuid

import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.common.exceptions import AegisException

logger = structlog.get_logger("aegis_ai.middleware")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global Error Handling & Request Tracing Middleware.

    For every request:
    - Generates a unique X-Request-ID for distributed tracing
    - Measures end-to-end processing time
    - Catches AegisException subclasses and returns correct HTTP status codes
    - Catches unhandled exceptions and returns 500 with sanitized error info
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind request context to structlog for all log calls within this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            process_ms = (time.perf_counter() - start_time) * 1000

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = f"{process_ms:.2f}"

            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(process_ms, 2),
            )
            return response

        except AegisException as exc:
            process_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "domain_exception",
                status_code=exc.status_code,
                message=exc.message,
                details=exc.details,
                duration_ms=round(process_ms, 2),
            )
            return JSONResponse(
                status_code=exc.status_code,
                headers={"X-Request-ID": request_id},
                content={
                    "success": False,
                    "status_code": exc.status_code,
                    "message": exc.message,
                    "data": None,
                    "error": exc.details or {"detail": exc.message},
                    "request_id": request_id,
                },
            )

        except Exception as exc:
            process_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "unhandled_system_exception",
                error=str(exc),
                exc_info=True,
                duration_ms=round(process_ms, 2),
            )
            # Never leak internal details in production
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                headers={"X-Request-ID": request_id},
                content={
                    "success": False,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "An unexpected internal server error occurred.",
                    "data": None,
                    "error": {"request_id": request_id},
                    "request_id": request_id,
                },
            )
