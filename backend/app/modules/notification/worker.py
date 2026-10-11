"""
AegisAI Notification Module â€” RabbitMQ Worker.

Consumes events from RabbitMQ and creates system alerts.
For example, when a new incident is created, an event is published,
and this worker consumes it to alert dispatchers.
"""

import asyncio
import json

import structlog

from app.core.config.settings import settings
from app.core.database.session import SessionLocal
from app.modules.notification.schemas import AlertCreate
from app.modules.notification.service import NotificationService

logger = structlog.get_logger("aegis_ai.notification.worker")


async def consume_events() -> None:
    """Consume simulation and incident events from RabbitMQ."""
    try:
        import aio_pika  # noqa: PLC0415
    except ImportError:
        logger.warning("aio_pika_not_installed_skipping_worker")
        return

    while True:
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                # Use a topic exchange
                exchange = await channel.declare_exchange(
                    settings.RABBITMQ_EXCHANGE, aio_pika.ExchangeType.TOPIC
                )

                # Declare a queue specifically for notifications
                queue = await channel.declare_queue("aegis_notifications_queue", durable=True)

                # Bind the queue to listen to incident events
                await queue.bind(exchange, routing_key="incident.#")

                logger.info("notification_worker_started", queue="aegis_notifications_queue")

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process():
                            await _process_message(message.routing_key, message.body)

        except Exception as e:
            logger.error("notification_worker_connection_error", error=str(e))
            await asyncio.sleep(5)  # Reconnect delay


async def _process_message(routing_key: str | None, body: bytes) -> None:
    """Process an incoming event and map it to an alert."""
    try:
        data = json.loads(body.decode())
    except json.JSONDecodeError:
        logger.error("notification_worker_invalid_json")
        return

    logger.debug("notification_event_received", routing_key=routing_key)

    if routing_key == "incident.created":
        # Create an alert for DISPATCHER and COMMANDER
        with SessionLocal() as db:
            payload = AlertCreate(
                title=f"New Incident: {data.get('disaster_type', 'Unknown')}",
                message=f"Severity: {data.get('severity', 'Unknown')}. Location: {data.get('latitude')}, {data.get('longitude')}",
                severity="WARNING" if data.get("severity") in ["HIGH", "CRITICAL"] else "INFO",
                target_role=None,  # Broadcast to all for now, or could iterate roles
            )
            # Create one for commanders
            payload.target_role = "COMMANDER"
            NotificationService.create_alert(db, payload)

            # Create one for dispatchers
            payload.target_role = "DISPATCHER"
            NotificationService.create_alert(db, payload)

    elif routing_key == "incident.status_changed":
        # Handle status change alerts
        pass
