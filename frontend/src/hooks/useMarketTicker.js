import { useWebSocket } from './useWebSocket';

/** Subscribes to a single ticker's live tick stream (/ws/market/{ticker}), public. */
export function useMarketTicker(ticker) {
  const { lastMessage, status } = useWebSocket(ticker ? `/ws/market/${ticker}` : null, {
    enabled: Boolean(ticker),
  });

  return { tick: lastMessage, connected: status === 'open' };
}
