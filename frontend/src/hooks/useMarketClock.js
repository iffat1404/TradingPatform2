import { useWebSocket } from './useWebSocket';

/**
 * Subscribes to the global MarketClock broadcast (/ws/session, 1s cadence).
 * Drives the topbar "process pulse" and market-status badge everywhere.
 */
export function useMarketClock() {
  const { lastMessage, status } = useWebSocket('/ws/session');

  return {
    simulatedTime: lastMessage?.simulated_time ?? null,
    speedMultiplier: lastMessage?.speed_multiplier ?? null,
    marketStatus: lastMessage?.market_status ?? null,
    sessionId: lastMessage?.session_id ?? null,
    connected: status === 'open',
  };
}
