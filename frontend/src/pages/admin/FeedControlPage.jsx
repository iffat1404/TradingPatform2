import { useEffect, useState } from 'react';
import {
  getFeedStatus,
  getSessionStatus,
  setSessionTime,
  resetSession,
  setSessionSpeed,
  resetFeed,
} from '../../api/admin';
import { useMarketClock } from '../../hooks/useMarketClock';
import { useToast } from '../../context/ToastContext';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { formatDateTime } from '../../utils/format';
import { extractErrorMessage } from '../../api/client';
import './admin-pages.css';

const SPEEDS = [1, 2, 5, 12, 30];

export function FeedControlPage() {
  const live = useMarketClock();
  const toast = useToast();
  const [feedStatus, setFeedStatus] = useState(null);
  const [dateValue, setDateValue] = useState(() => new Date().toISOString().slice(0, 10));
  const [timeValue, setTimeValue] = useState('09:30:00');
  const [busy, setBusy] = useState(false);

  const refresh = () => {
    Promise.all([getFeedStatus().catch(() => null), getSessionStatus().catch(() => null)]).then(([feed]) => {
      setFeedStatus(feed);
    });
  };

  useEffect(refresh, []);

  const runAction = async (label, action) => {
    setBusy(true);
    try {
      await action();
      toast.success(`${label} applied.`);
      refresh();
    } catch (err) {
      toast.error(extractErrorMessage(err, `Could not ${label.toLowerCase()}.`));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Feed & session control</h2>
          <p className="page-subtitle">
            The MarketClock is the platform's single source of truth for time — every trader sees exactly this.
          </p>
        </div>
      </div>

      <Card title="Live status">
        <div className="feed-readout">
          <div className="feed-readout-item">
            <span className="eyebrow">Simulated time</span>
            <span className="mono-num" style={{ fontSize: 20 }}>
              {live.simulatedTime ? formatDateTime(live.simulatedTime) : '—'}
            </span>
          </div>
          <div className="feed-readout-item">
            <span className="eyebrow">Market status</span>
            <span className={`badge badge-${live.marketStatus === 'open' ? 'positive' : live.marketStatus === 'closed' ? 'negative' : 'neutral'}`}>
              {live.marketStatus || '—'}
            </span>
          </div>
          <div className="feed-readout-item">
            <span className="eyebrow">Speed</span>
            <span className="mono-num">{live.speedMultiplier ?? '—'}×</span>
          </div>
          <div className="feed-readout-item">
            <span className="eyebrow">Session ID</span>
            <span className="font-mono" style={{ fontSize: 12 }}>
              {live.sessionId || '—'}
            </span>
          </div>
          <div className="feed-readout-item">
            <span className="eyebrow">Connection</span>
            <span className={`badge ${live.connected ? 'badge-positive' : 'badge-negative'}`}>
              {live.connected ? 'live' : 'reconnecting'}
            </span>
          </div>
        </div>
      </Card>

      <Card title="Replay speed">
        <div className="speed-btn-row">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              className={`speed-btn${live.speedMultiplier === s ? ' is-active' : ''}`}
              disabled={busy}
              onClick={() => runAction('Speed change', () => setSessionSpeed(s))}
            >
              {s}×
            </button>
          ))}
        </div>
      </Card>

      <div className="two-col">
        <Card title="Set session time">
          <div className="filters-row">
            <div className="field">
              <label>Date</label>
              <input className="input" type="date" value={dateValue} onChange={(e) => setDateValue(e.target.value)} />
            </div>
            <div className="field">
              <label>Time (UTC)</label>
              <input className="input" type="time" step="1" value={timeValue} onChange={(e) => setTimeValue(e.target.value)} />
            </div>
            <Button disabled={busy} onClick={() => runAction('Session time', () => setSessionTime(dateValue, timeValue))}>
              Apply
            </Button>
          </div>
        </Card>

        <Card title="Reset">
          <div className="stack" style={{ gap: 12 }}>
            <p className="field-hint">Reset session returns the MarketClock to the start of the dataset.</p>
            <button className="btn btn-secondary" type="button" disabled={busy} onClick={() => runAction('Session reset', resetSession)}>
              Reset session
            </button>
            <p className="field-hint">Reset feed returns the price feed simulator to the start of the dataset.</p>
            <button className="btn btn-secondary" type="button" disabled={busy} onClick={() => runAction('Feed reset', resetFeed)}>
              Reset feed
            </button>
          </div>
        </Card>
      </div>

    </div>
  );
}
