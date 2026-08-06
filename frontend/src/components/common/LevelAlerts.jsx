import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLevelAlerts, acknowledgeLevelAlert } from '../../api/levels';
import { useMarketClock } from '../../hooks/useMarketClock';
import './LevelAlerts.css';

/**
 * Banner telling the trader their own target or stop has been reached.
 *
 * When a level is hit, the position is automatically sold at market price.
 * The alert informs the trader that their position has been closed according to their plan.
 */

const POLL_MS = 20000;

export function LevelAlerts() {
  const navigate = useNavigate();
  const clock = useMarketClock();
  const [alerts, setAlerts] = useState([]);

  // Re-check as the simulated minute advances, plus a slow poll as a safety net.
  const simMinute = clock.simulatedTime ? clock.simulatedTime.slice(0, 16) : null;

  useEffect(() => {
    let active = true;
    const load = () =>
      getLevelAlerts()
        .then((res) => active && setAlerts(res.alerts || []))
        .catch(() => {});
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [simMinute]);

  const dismiss = async (id) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
    try {
      await acknowledgeLevelAlert(id);
    } catch {
      /* the next poll will bring it back if this failed */
    }
  };

  const visible = alerts.filter((a) => !a.acknowledged);
  if (!visible.length) return null;

  return (
    <div className="level-alerts">
      {visible.map((a) => (
        <div className={`level-alert level-alert-${a.kind}${a.auto_sold ? ' auto-sold' : ''}`} key={a.id} role="status">
          <span className="level-alert-kind">{a.kind === 'stop' ? 'Stop hit' : 'Target hit'}</span>
          <span className="level-alert-msg">{a.message}</span>
          <span className="level-alert-action">{a.action}</span>
          {a.auto_sold && (
            <span className="level-alert-auto-sold">✓ {a.auto_sold_info}</span>
          )}
          <div className="level-alert-buttons">
            {!a.auto_sold && (
              <button
                className="btn btn-secondary btn-sm"
                type="button"
                onClick={() => navigate('/trader/trade', { state: { prefill: { ticker: a.ticker, side: a.signed_qty > 0 ? 'sell' : 'buy' } } })}
              >
                Review position
              </button>
            )}
            <button className="btn btn-ghost btn-sm" type="button" onClick={() => dismiss(a.id)}>
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
