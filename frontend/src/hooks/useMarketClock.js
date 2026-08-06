import { useAuth } from '../context/AuthContext';
import { useWebSocket } from './useWebSocket';

/**
 * Subscribes to the global MarketClock broadcast (/ws/session, 1s cadence).
 * Drives the topbar "process pulse" and market-status badge everywhere.
 * Only connects after the user is authenticated to avoid connection errors during init.
 */
export function useMarketClock() {
  const { isAuthenticated } = useAuth();
  const { lastMessage, status } = useWebSocket('/ws/session', { enabled: isAuthenticated });

  return {
    simulatedTime: lastMessage?.simulated_time ?? null,
    speedMultiplier: lastMessage?.speed_multiplier ?? null,
    marketStatus: lastMessage?.market_status ?? null,
    sessionId: lastMessage?.session_id ?? null,
    connected: status === 'open',
  };
}
