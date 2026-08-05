import { useEffect, useRef, useState } from 'react';
import { wsBaseUrl } from '../api/client';

const MAX_BACKOFF_MS = 30000;

/**
 * Generic reconnecting WebSocket subscriber.
 * `path` is relative, e.g. "/ws/session" or "/ws/market/AAPL".
 */
export function useWebSocket(path, { enabled = true } = {}) {
  const [lastMessage, setLastMessage] = useState(null);
  const [status, setStatus] = useState('idle');

  useEffect(() => {
    if (!enabled || !path) {
      setStatus('idle');
      return undefined;
    }

    let cancelled = false;
    let socket = null;
    let timer = null;
    let attempt = 0;

    const teardown = () => {
      if (!socket) return;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      try {
        socket.close();
      } catch {
        /* already closing */
      }
      socket = null;
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      const delay = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS);
      attempt += 1;
      timer = setTimeout(connect, delay);
    };

    function connect() {
      if (cancelled) return;
      setStatus('connecting');
      try {
        socket = new WebSocket(`${wsBaseUrl}${path}`);
      } catch (err) {
        socket = null;
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (cancelled) return;
        attempt = 0;
        setStatus('open');
      };
      socket.onmessage = (event) => {
        if (cancelled) return;
        try {
          setLastMessage(JSON.parse(event.data));
        } catch {
          setLastMessage(event.data);
        }
      };
      socket.onclose = () => {
        if (cancelled) return;
        setStatus('closed');
        socket = null;
        scheduleReconnect();
      };
      socket.onerror = () => {
        if (cancelled) return;
        // onclose always follows onerror; let it drive the reconnect
        try {
          socket?.close();
        } catch {
          /* noop */
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(timer);
      teardown();
    };
  }, [path, enabled]);

  return { lastMessage, status };
}
