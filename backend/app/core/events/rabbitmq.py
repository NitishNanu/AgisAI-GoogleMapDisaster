"""
AegisAI Core — RabbitMQ Event Bus Publisher.

Provides asynchronous, non-blocking publishing of domain events (e.g. incident updates,
resource dispatches, simulation ticks) to RabbitMQ via aio-pika.
Falls back gracefully if RabbitMQ is not available or offline.
"""

import asyncio
import json
import time
from typing import Any

import structlog

from app.core.config.settings import settings

logger = structlog.get_logger("aegis_ai.core.events.rabbitmq")

_connection: Any = None
_channel: Any = None
_exchange: Any = None
_last_failure_time: float = 0.0
FAILURE_COOLDOWN_SECONDS: float = 30.0


def get_rabbitmq_url() -> str:
    """Construct RabbitMQ connection URL from settings."""
    user = settings.RABBITMQ_USER
    password = settings.RABBITMQ_PASSWORD
    host = settings.RABBITMQ_HOST
    port = settings.RABBITMQ_PORT
    vhost = settings.RABBITMQ_VHOST.lstrip("/")
    return f"amqp://{user}:{password}@{host}:{port}/{vhost}"


def is_broker_accessible() -> bool:
    """Fast TCP socket probe to verify broker port is open without blocking async event loops."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        res = sock.connect_ex((settings.RABBITMQ_HOST, settings.RABBITMQ_PORT))
        sock.close()
        return res == 0
    except Exception:
        return False


async def get_exchange() -> Any:
    """Lazily initialize connection, channel, and topic exchange with fast-fail circuit breaker."""
    global _connection, _channel, _exchange, _last_failure_time

    if _exchange is not None and _channel and not _channel.is_closed:
        return _exchange

    # Circuit breaker: don't stall the event loop if recently unreachable
    now = time.time()
    if now - _last_failure_time < FAILURE_COOLDOWN_SECONDS:
        return None

    # Instant TCP port probe before attempting aio_pika AMQP handshake
    if not is_broker_accessible():
        _last_failure_time = now
        logger.debug("rabbitmq_broker_unreachable_degraded")
        return None

    try:
        import aio_pika

        # Use fast timeout socket connect (0.5s) instead of infinite connect_robust retry loop
        _connection = await asyncio.wait_for(
            aio_pika.connect(get_rabbitmq_url()),
            timeout=0.5,
        )
        _channel = await _connection.channel()
        _exchange = await _channel.declare_exchange(
            name=settings.RABBITMQ_EXCHANGE,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("rabbitmq_connected", exchange=settings.RABBITMQ_EXCHANGE)
        return _exchange
    except Exception as exc:
        _last_failure_time = time.time()
        logger.warning("rabbitmq_connection_failed_degraded", error=str(exc))
        _exchange = None
        _channel = None
        _connection = None
        return None


async def publish_event(routing_key: str, payload: dict[str, Any]) -> bool:
    """
    Publish an event message to RabbitMQ exchange.
    Returns True if successfully delivered to exchange, False otherwise.
    Never throws an exception so callers are not blocked.
    """
    try:
        exchange = await get_exchange()
        if exchange is None:
            return False

        import aio_pika

        body = json.dumps(payload, default=str).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await asyncio.wait_for(exchange.publish(message, routing_key=routing_key), timeout=0.5)
        logger.debug("rabbitmq_event_published", routing_key=routing_key)
        return True
    except Exception as exc:
        logger.warning("rabbitmq_publish_error", routing_key=routing_key, error=str(exc))
        return False


async def close_rabbitmq() -> None:
    """Cleanly close RabbitMQ connection on application shutdown."""
    global _connection, _channel, _exchange
    try:
        if _channel and not _channel.is_closed:
            await _channel.close()
        if _connection and not _connection.is_closed:
            await _connection.close()
    except Exception as exc:
        logger.debug("rabbitmq_close_error", error=str(exc))
    finally:
        _channel = None
        _connection = None
        _exchange = None
