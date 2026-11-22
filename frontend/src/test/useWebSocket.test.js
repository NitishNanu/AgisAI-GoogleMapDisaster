import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../hooks/useWebSocket';
import useMapStore from '../store/useMapStore';

// Mock WebSocket
class MockWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3; // CLOSED
    if (this.onclose) this.onclose();
  });
}

describe('useWebSocket hook', () => {
  let originalWebSocket;

  beforeEach(() => {
    originalWebSocket = global.WebSocket;
    global.WebSocket = MockWebSocket;
    MockWebSocket.instances = [];
    vi.useFakeTimers();
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    vi.useRealTimers();
  });

  it('connects to URL with auth token and updates status to CONNECTED', () => {
    const { result } = renderHook(() =>
      useWebSocket('ws://localhost:8000/ws/v1/stream', 'test-jwt-token')
    );

    expect(MockWebSocket.instances.length).toBe(1);
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('token=test-jwt-token');

    act(() => {
      ws.readyState = 1; // OPEN
      ws.onopen();
    });

    expect(result.current.status).toBe('CONNECTED');
  });

  it('handles SIMULATION_TICK_DELTA message and applies to map store', () => {
    const applyDeltasSpy = vi.spyOn(useMapStore.getState(), 'applyDeltas');

    renderHook(() =>
      useWebSocket('ws://localhost:8000/ws/v1/stream', 'test-jwt-token')
    );

    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.readyState = 1;
      ws.onopen();
      ws.onmessage({
        data: JSON.stringify({
          event: 'SIMULATION_TICK_DELTA',
          payload: { citizens: [{ id: 1, lat: 30.7, lon: 76.7 }] },
        }),
      });
    });

    expect(applyDeltasSpy).toHaveBeenCalledWith({
      citizens: [{ id: 1, lat: 30.7, lon: 76.7 }],
    });
  });

  it('transitions to RECONNECTING on connection close and triggers reconnect', () => {
    const { result } = renderHook(() =>
      useWebSocket('ws://localhost:8000/ws/v1/stream', 'test-jwt-token')
    );

    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.readyState = 1;
      ws.onopen();
    });
    expect(result.current.status).toBe('CONNECTED');

    // Simulate unexpected server disconnect
    act(() => {
      ws.onclose();
    });

    expect(result.current.status).toBe('RECONNECTING');

    // Fast-forward reconnect backoff timer
    act(() => {
      vi.advanceTimersByTime(1500);
    });

    // A second WebSocket instance should have been created
    expect(MockWebSocket.instances.length).toBeGreaterThan(1);
  });
});
