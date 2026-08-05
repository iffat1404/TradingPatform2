import { useEffect, useRef, useCallback } from 'react';

let globalNewsWs = null;
const newsListeners = new Set();

function connectGlobalNewsStream() {
  if (globalNewsWs && globalNewsWs.readyState === WebSocket.OPEN) {
    return globalNewsWs;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  const url = `${protocol}://${host}/ws/news/all`;

  try {
    globalNewsWs = new WebSocket(url);

    globalNewsWs.onopen = () => {
      console.log('Connected to global news stream');
    };

    globalNewsWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'news_update') {
          newsListeners.forEach((listener) => listener(data));
        }
      } catch (err) {
        console.error('Error parsing news message:', err);
      }
    };

    globalNewsWs.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    globalNewsWs.onclose = () => {
      console.log('Disconnected from global news stream');
      globalNewsWs = null;
      setTimeout(() => {
        connectGlobalNewsStream();
      }, 3000);
    };
  } catch (err) {
    console.error('Error connecting to news WebSocket:', err);
  }

  return globalNewsWs;
}

export function useNewsStream(onNewsUpdate) {
  useEffect(() => {
    connectGlobalNewsStream();

    if (onNewsUpdate) {
      newsListeners.add(onNewsUpdate);
    }

    return () => {
      if (onNewsUpdate) {
        newsListeners.delete(onNewsUpdate);
      }
    };
  }, [onNewsUpdate]);

  return globalNewsWs;
}

