"""
AegisAI Structured Logging Configuration.

Configures structlog for production JSON logging. Integrates with Python's
standard library logging so that third-party library logs (SQLAlchemy,
uvicorn, httpx) are also captured in the same structured format.

Usage:
    from app.core.common.logging import logger, setup_logging

    setup_logging()  # call once at startup

    logger.info("event_name", key="value", request_id="abc123")
"""

import logging
import sys

import structlog

from app.core.config.settings import settings


def setup_logging() -> None:
    """
    Configure structlog for production structured JSON logging.

    In DEBUG mode, outputs colorized key-value logs to stdout.
    In production, outputs pure JSON for log aggregators (Datadog, ELK, etc).
    """
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Processors shared between structlog and stdlib integration
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer() if not settings.DEBUG else structlog.dev.ConsoleRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress noisy third-party loggers in production
    if not settings.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("apscheduler").setLevel(logging.WARNING)


# Module-level logger — importable directly across the codebase
logger: structlog.stdlib.BoundLogger = structlog.get_logger("aegis_ai")
