import { useEffect, useRef, useState, useCallback } from 'react';
import useMapStore from '../store/useMapStore';

export function useWebSocket(url, token) {
    const [status, setStatus] = useState('DISCONNECTED');
    const wsRef = useRef(null);
    const reconnectAttempts = useRef(0);
    const connectRef = useRef(null);
    const maxReconnectDelay = 30000;

    const connect = useCallback(() => {
        if (!token) return;

        setStatus('CONNECTING');
        const wsUrl = new URL(url);
        wsUrl.searchParams.append('token', token);

        const ws = new WebSocket(wsUrl.toString());
        wsRef.current = ws;

        ws.onopen = () => {
            setStatus('CONNECTED');
            reconnectAttempts.current = 0;
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                // Process deltas
                if (data.event === 'SIMULATION_TICK_DELTA') {
                    useMapStore.getState().applyDeltas(data.payload);
                }
            } catch (error) {
                console.error("WS Parse error", error);
            }
        };

        ws.onclose = () => {
            setStatus('RECONNECTING');
            // Exponential backoff
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), maxReconnectDelay);
            reconnectAttempts.current += 1;
            setTimeout(() => {
                if (connectRef.current) {
                    connectRef.current();
                }
            }, delay);
        };

        ws.onerror = (err) => {
            console.error("WS Error", err);
            ws.close();
        };
    }, [url, token]);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    useEffect(() => {
        connect();
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [connect]);

    const sendPayload = useCallback((action, payload = {}) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                action,
                token, // Attach JWT to every payload
                ...payload
            }));
        } else {
            console.warn("WebSocket not connected. Unable to send:", action);
        }
    }, [token]);

    return { status, sendPayload };
}
