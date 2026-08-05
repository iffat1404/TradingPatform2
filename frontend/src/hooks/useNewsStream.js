import { useEffect, useRef, useCallback } from 'react';
import { useMarketClock } from './useMarketClock';

export function useNewsStream(ticker, onNewsUpdate) {
  const ws = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const clock = useMarketClock();

  const connect = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;
    const url = `${protocol}://${host}/ws/news/${ticker}`;

    try {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        console.log(`Connected to news stream for ${ticker}`);
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'news_update' && onNewsUpdate) {
            onNewsUpdate(data);
          }
        } catch (err) {
          console.error('Error parsing news message:', err);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.current.onclose = () => {
        console.log(`Disconnected from news stream for ${ticker}`);
        // Attempt reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };
    } catch (err) {
      console.error('Error connecting to news WebSocket:', err);
    }
  }, [ticker, onNewsUpdate]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (ws.current) {
        try {
          ws.current.close();
        } catch (e) {
          console.error('Error closing WebSocket:', e);
        }
      }
    };
  }, [ticker, connect]);

  return ws.current;
}
