import { useMarketClock } from '../../hooks/useMarketClock';
import { formatTime } from '../../utils/format';
import './MarketPulse.css';

const STATUS_TONE = {
  open: 'positive',
  'pre-market': 'neutral',
  closed: 'negative',
};

export function MarketPulse() {
  const { simulatedTime, speedMultiplier, marketStatus, connected } = useMarketClock();
  const tone = STATUS_TONE[marketStatus] || 'neutral';

  return (
    <div className="market-pulse" title="MarketClock — the platform's single authoritative time source">
      <span className={`pulse-dot${connected ? ' is-live' : ''}`} />
      <span className="mono-num pulse-time">{simulatedTime ? formatTime(simulatedTime) : '--:--:--'}</span>
      {marketStatus ? <span className={`badge badge-${tone}`}>{marketStatus}</span> : null}
      {speedMultiplier && speedMultiplier !== 1 ? <span className="pulse-speed mono-num">{speedMultiplier}×</span> : null}
    </div>
  );
}
