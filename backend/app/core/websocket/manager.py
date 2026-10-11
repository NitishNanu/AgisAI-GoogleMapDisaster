from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger("aegis_ai.websocket.manager")


class WebSocketConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[str]] = {
            "simulation": set(),
            "missions": set(),
            "incidents": set(),
            "predictions": set(),
            "all": set(),
        }

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions["all"].add(client_id)
        logger.info("websocket_client_connected", client_id=client_id, total=len(self.active_connections))

    def disconnect(self, client_id: str) -> None:
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        for channel in self.subscriptions:
            self.subscriptions[channel].discard(client_id)
        logger.info("websocket_client_disconnected", client_id=client_id, total=len(self.active_connections))

    def subscribe(self, client_id: str, channel: str) -> None:
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()
        self.subscriptions[channel].add(client_id)
        logger.info("websocket_subscribed", client_id=client_id, channel=channel)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        if channel in self.subscriptions:
            self.subscriptions[channel].discard(client_id)
        logger.info("websocket_unsubscribed", client_id=client_id, channel=channel)

    async def send_personal_message(self, client_id: str, message: dict[str, Any]) -> None:
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("websocket_send_failed", client_id=client_id, error=str(e))
                self.disconnect(client_id)

    async def broadcast_to_channel(self, channel: str, event_type: str, data: Any) -> None:
        recipients = self.subscriptions.get(channel, set()) | self.subscriptions.get("all", set())
        if not recipients:
            return

        payload = {
            "event": event_type,
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        dead_clients = []
        for client_id in recipients:
            ws = self.active_connections.get(client_id)
            if ws:
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    logger.warning("websocket_broadcast_error", client_id=client_id, error=str(e))
                    dead_clients.append(client_id)

        for client_id in dead_clients:
            self.disconnect(client_id)


ws_manager = WebSocketConnectionManager()
