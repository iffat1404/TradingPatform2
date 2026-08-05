import { useEffect, useState } from 'react';
import { getMarketCurrent, TICKERS } from '../../api/prices';
import { useMarketClock } from '../../hooks/useMarketClock';
import { formatCurrency, formatPercent, deltaClass } from '../../utils/format';
import './TickerTape.css';

export function TickerTape() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const { marketStatus } = useMarketClock();

  useEffect(() => {
    let active = true;
    const load = () => {
      getMarketCurrent()
        .then((res) => {
          if (!active) return;
          setData(res);
          setFailed(false);
        })
        .catch(() => {
          if (active) setFailed(true);
        });
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const rows = TICKERS.map((ticker) => ({ ticker, row: data?.[ticker] })).filter((r) => r.row);

  if (!rows.length) {
    // No ticks isn't always a failure: the simulator only has minute-level data during
    // trading hours, so "market closed" is an expected, common state — not an error.
    const marketShut = !failed && (marketStatus === 'closed' || marketStatus === 'pre-market');
    const message = failed
      ? 'Live feed unavailable — the market data service is not responding. Retrying every 15s.'
      : marketShut
        ? `Markets are ${marketStatus === 'pre-market' ? 'in pre-market' : 'closed'} — the tape resumes at the next open (09:30 UTC).`
        : 'Connecting to live feed…';
    return (
      <div className="ticker-tape">
        <span className={`ticker-live-dot${failed ? ' is-down' : marketShut ? ' is-closed' : ' is-connecting'}`} />
        <span className="loading-row">{message}</span>
      </div>
    );
  }

  const items = rows.map(({ ticker, row }) => {
    const change = row.close - row.open;
    const changePct = row.open ? (change / row.open) * 100 : 0;
    return { ticker, price: row.close, changePct };
  });

  const renderItems = (keyPrefix) =>
    items.map((item) => (
      <span className="ticker-item" key={`${keyPrefix}-${item.ticker}`}>
        <span className="ticker-symbol">{item.ticker}</span>
        <span className="mono-num ticker-price">{formatCurrency(item.price)}</span>
        <span className={`mono-num ticker-change ${deltaClass(item.changePct)}`}>
          {item.changePct >= 0 ? '▲' : '▼'} {formatPercent(item.changePct)}
        </span>
      </span>
    ));

  return (
    <div className="ticker-tape">
      <span className="ticker-live-badge">
        <span className="ticker-live-dot is-live" />
        LIVE
      </span>
      <div className="ticker-scroll-area">
        <div className="ticker-track">
          {renderItems('a')}
          {renderItems('b')}
        </div>
      </div>
    </div>
  );
}
