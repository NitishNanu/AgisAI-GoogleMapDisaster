/**
 * AegisAI Centralized Real-time WebSocket Connection Manager
 * Features:
 * - Singleton connection lifecycle
 * - Exponential backoff auto-reconnect (1s -> 2s -> 4s -> 8s -> 16s -> max 30s)
 * - Channel subscriptions ("all", "incidents", "missions", "simulation")
 * - Event Pub/Sub listener registry
 * - 25s ping/pong keepalive heartbeat
 * - Connection status state machine: CONNECTING | CONNECTED | DISCONNECTED | RECONNECTING | ERROR
 */

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000";

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.status = "DISCONNECTED"; // CONNECTING | CONNECTED | DISCONNECTED | RECONNECTING | ERROR
        this.listeners = new Map(); // eventName -> Set(callbacks)
        this.statusListeners = new Set(); // callback(status)
        this.retryCount = 0;
        this.maxRetryDelay = 30000; // 30s max backoff
        this.reconnectTimer = null;
        this.pingTimer = null;
        this.isExplicitlyClosed = false;
        this.clientId = null;
    }

    /**
     * Connect to the AegisAI telemetry stream
     */
    connect(token = null) {
        // Do NOT attempt connection without a token — the backend requires JWT auth.
        if (!token) {
            return;
        }

        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.isExplicitlyClosed = false;
        this.setStatus(this.retryCount > 0 ? "RECONNECTING" : "CONNECTING");

        try {
            const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
            const wsUrl = `${WS_BASE_URL}/ws/v1/stream${tokenParam}`;
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                this.retryCount = 0;
                this.setStatus("CONNECTED");
                this.startHeartbeat();

                // Subscribe to core channels
                this.send({ action: "subscribe", channel: "all" });
                this.send({ action: "subscribe", channel: "incidents" });
                this.send({ action: "subscribe", channel: "missions" });
                this.send({ action: "subscribe", channel: "simulation" });
                this.send({ action: "subscribe", channel: "predictions" });
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleIncomingMessage(message);
                } catch (err) {
                    console.warn("[WebSocket] Failed to parse message:", err);
                }
            };

            this.ws.onerror = (err) => {
                console.warn("[WebSocket] Connection error:", err);
                this.setStatus("ERROR");
            };

            this.ws.onclose = (_event) => {
                this.stopHeartbeat();
                this.ws = null;

                if (!this.isExplicitlyClosed) {
                    this.setStatus("DISCONNECTED");
                    this.scheduleReconnect(token);
                } else {
                    this.setStatus("DISCONNECTED");
                }
            };
        } catch (err) {
            console.error("[WebSocket] Exception during connect:", err);
            this.setStatus("ERROR");
            this.scheduleReconnect(token);
        }
    }

    /**
     * Schedule reconnection with exponential backoff
     */
    scheduleReconnect(token) {
        // No token means nothing to reconnect to — bail out silently.
        if (!token || this.reconnectTimer || this.isExplicitlyClosed) {
            return;
        }

        // Calculate backoff: min(1000 * 2^retries, 30000)
        const delay = Math.min(1000 * Math.pow(2, this.retryCount), this.maxRetryDelay);
        this.retryCount++;
        this.setStatus("RECONNECTING");

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect(token);
        }, delay);
    }

    /**
     * Disconnect intentionally
     */
    disconnect() {
        this.isExplicitlyClosed = true;
        this.stopHeartbeat();
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.setStatus("DISCONNECTED");
    }

    /**
     * Send JSON frame
     */
    send(payload) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(payload));
        }
    }

    /**
     * Heartbeat keepalive every 25s
     */
    startHeartbeat() {
        this.stopHeartbeat();
        this.pingTimer = setInterval(() => {
            this.send({ action: "ping", timestamp: Date.now() });
        }, 25000);
    }

    stopHeartbeat() {
        if (this.pingTimer) {
            clearInterval(this.pingTimer);
            this.pingTimer = null;
        }
    }

    /**
     * Dispatch incoming event to registered event listeners
     */
    handleIncomingMessage(message) {
        const eventType = message.event || message.action || "message";

        if (eventType === "connection_established") {
            this.clientId = message.client_id;
        }

        // 1. Notify specific event listeners
        if (this.listeners.has(eventType)) {
            this.listeners.get(eventType).forEach((callback) => {
                try {
                    callback(message.data !== undefined ? message.data : message);
                } catch (cbErr) {
                    console.error(`[WebSocket] Callback error on event ${eventType}:`, cbErr);
                }
            });
        }

        // 2. Notify wildcard '*' listeners
        if (this.listeners.has("*")) {
            this.listeners.get("*").forEach((callback) => {
                try {
                    callback(message);
                } catch (cbErr) {
                    console.error("[WebSocket] Wildcard callback error:", cbErr);
                }
            });
        }
    }

    /**
     * Subscribe to a specific message event type
     * @param {string} eventType e.g. "INCIDENT_CREATED", "MISSION_UPDATED", "SIMULATION_TICK", or "*"
     * @param {Function} callback function receiving the event data payload
     * @returns {Function} unsubscribe unregister function
     */
    subscribe(eventType, callback) {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, new Set());
        }
        this.listeners.get(eventType).add(callback);

        return () => {
            if (this.listeners.has(eventType)) {
                this.listeners.get(eventType).delete(callback);
            }
        };
    }

    /**
     * Subscribe to connection status changes
     * @param {Function} callback receiving "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "RECONNECTING" | "ERROR"
     */
    onStatusChange(callback) {
        this.statusListeners.add(callback);
        // Immediately notify with current status
        callback(this.status);

        return () => {
            this.statusListeners.delete(callback);
        };
    }

    setStatus(newStatus) {
        if (this.status !== newStatus) {
            this.status = newStatus;
            this.statusListeners.forEach((callback) => {
                try {
                    callback(newStatus);
                } catch (err) {
                    console.error("[WebSocket] Status listener error:", err);
                }
            });
        }
    }

    getStatus() {
        return this.status;
    }
}

export const wsManager = new WebSocketManager();
export default wsManager;
