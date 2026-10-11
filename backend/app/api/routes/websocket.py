import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.config.settings import settings
from app.core.websocket.manager import ws_manager

logger = structlog.get_logger("aegis_ai.api.websocket")

router = APIRouter(tags=["Real-time Telemetry WebSocket"])

# WebSocket close codes
_WS_POLICY_VIOLATION = 1008  # Used for auth failures


def _validate_ws_token(token: str | None) -> dict[str, Any] | None:
    """
    Decode and validate a JWT token for WebSocket authentication.

    Returns the decoded payload on success, or None if the token is
    missing / invalid / expired. Deliberately does NOT raise — the caller
    decides how to handle the failure so the WebSocket handshake can be
    rejected cleanly.
    """
    if not token or token.strip() in ("", "null", "undefined", "None"):
        return None
    try:
        from jose import jwt  # noqa: PLC0415

        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        if not payload.get("sub"):
            return None
        return payload
    except JWTError:
        return None



async def get_ws_user(websocket: WebSocket, token: str | None = Query(default=None)):
    payload = _validate_ws_token(token)
    if not payload:
        await websocket.close(code=_WS_POLICY_VIOLATION, reason="Authentication required.")
        return None
    return payload

@router.websocket("/ws/v1/stream")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    client_id: str | None = Query(default=None),
    user_payload: dict[str, Any] | None = Depends(get_ws_user),
) -> None:
    if user_payload is None:
        return

    user_id = user_payload.get("sub")
    user_role = user_payload.get("role", "CITIZEN")

    assigned_client_id = client_id or str(uuid.uuid4())
    await ws_manager.connect(assigned_client_id, websocket)

    await ws_manager.send_personal_message(
        assigned_client_id,
        {
            "event": "connection_established",
            "client_id": assigned_client_id,
            "user_id": user_id,
            "role": user_role,
            "channels": ["simulation", "missions", "incidents", "all"],
            "message": "Connected to AegisAI Live Telemetry Stream.",
        },
    )

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            # Verify token on every payload
            payload_token = data.get("token")
            payload = _validate_ws_token(payload_token)
            if not payload:
                await ws_manager.send_personal_message(
                    assigned_client_id, {"event": "error", "message": "Invalid token on payload"}
                )
                continue

            current_role = payload.get("role", "CITIZEN")

            if action == "subscribe":
                channel = data.get("channel", "all")
                ws_manager.subscribe(assigned_client_id, channel)
                await ws_manager.send_personal_message(
                    assigned_client_id,
                    {"event": "subscription_confirmed", "channel": channel},
                )

            elif action == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    ws_manager.unsubscribe(assigned_client_id, channel)
                    await ws_manager.send_personal_message(
                        assigned_client_id,
                        {"event": "unsubscription_confirmed", "channel": channel},
                    )

            elif action == "ping":
                await ws_manager.send_personal_message(
                    assigned_client_id,
                    {"event": "pong", "timestamp": data.get("timestamp")},
                )

            elif action == "Spawn Incident":
                if current_role not in ["COMMANDER", "ADMIN", "DISPATCHER"]:
                    await ws_manager.send_personal_message(assigned_client_id, {"event": "error", "message": "RBAC Denied"})
                    continue
                # Spawn logic
                from app.modules.simulation.engine import engine
                engine.force_add_disaster(data.get("lat"), data.get("lon"), data.get("severity", "HIGH"))
                await ws_manager.send_personal_message(assigned_client_id, {"event": "incident_spawned"})

            elif action == "Launch Simulation":
                if current_role not in ["ADMIN", "COMMANDER"]:
                    await ws_manager.send_personal_message(assigned_client_id, {"event": "error", "message": "RBAC Denied"})
                    continue
                # Launch logic
                from app.modules.simulation.scheduler import scheduler
                if not scheduler.running:
                    scheduler.start()
                await ws_manager.send_personal_message(assigned_client_id, {"event": "simulation_launched"})

    except WebSocketDisconnect:
        ws_manager.disconnect(assigned_client_id)
    except Exception as e:
        logger.warning("websocket_session_error", client_id=assigned_client_id, error=str(e))
        ws_manager.disconnect(assigned_client_id)

