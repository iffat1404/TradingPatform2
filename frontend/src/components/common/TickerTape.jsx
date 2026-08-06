import { useEffect, useState } from 'react';
import { getMarketCurrent, TICKERS, getPlatformQuotes } from '../../api/prices';
import { useMarketClock } from '../../hooks/useMarketClock';
import { formatCurrency, formatPercent, deltaClass, calculateTickerChange, calculateIntradayChange } from '../../utils/format';
import './TickerTape.css';

export function TickerTape() {
  const [data, setData] = useState(null);
  const [quotes, setQuotes] = useState({});
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

  useEffect(() => {
    if (!data) return;
    let active = true;
    const fetchQuotes = async () => {
      const quotesData = {};
      for (const ticker of TICKERS) {
        try {
          const quote = await getPlatformQuotes(ticker);
          if (active) {
            quotesData[ticker] = quote;
          }
        } catch (err) {
          // Skip failed quotes
        }
      }
      if (active) {
        setQuotes(quotesData);
      }
    };
    fetchQuotes();
    return () => {
      active = false;
    };
  }, [data]);

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
    // Standard ticker change % against previous close
    const changePct = calculateTickerChange(row.close, row.previous_close || row.open);
    // Intraday change (current price - today's open)
    const intradayChange = calculateIntradayChange(row.close, row.open);
    const quote = quotes[ticker];
    return { ticker, price: row.close, changePct, intradayChange, quote };
  });

  const renderItems = (keyPrefix) =>
    items.map((item) => (
      <span className="ticker-item" key={`${keyPrefix}-${item.ticker}`} title={item.quote ? `B: ${formatCurrency(item.quote.bid)} / A: ${formatCurrency(item.quote.ask)}` : ''}>
        <span className="ticker-symbol">{item.ticker}</span>
        <span className="mono-num ticker-price">{formatCurrency(item.price)}</span>
        {item.quote && (
          <span className="mono-num ticker-spread" title={`Spread: ${formatCurrency(item.quote.spread)}`}>
            B: {formatCurrency(item.quote.bid)} / A: {formatCurrency(item.quote.ask)}
          </span>
        )}
        <span className={`mono-num ticker-change ${deltaClass(item.changePct)}`}>
          {item.changePct >= 0 ? '▲' : '▼'} {formatPercent(item.changePct)}
        </span>
        <span className={`mono-num ticker-intraday ${deltaClass(item.intradayChange)}`}>
          {item.intradayChange >= 0 ? '+' : ''}{formatCurrency(item.intradayChange)}
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
