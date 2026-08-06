import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listNews } from '../../api/news';
import { useMarketClock } from '../../hooks/useMarketClock';
import './NewsFeed.css';

/**
 * The news actually driving the simulated market.
 *
 * Each headline carries its own per-ticker sentiment and a relevance score, so a passing
 * mention reads differently from a story that is genuinely about that company. "Journal
 * this" carries the headline into a journal entry, which is what later lets the coach ask
 * whether the news you traded on really moved the price.
 */

const TONE = {
  Bullish: 'positive',
  'Somewhat-Bullish': 'positive',
  Neutral: 'neutral',
  'Somewhat-Bearish': 'negative',
  Bearish: 'negative',
};

const SHORT_LABEL = {
  Bullish: 'Bullish',
  'Somewhat-Bullish': 'Mildly bullish',
  Neutral: 'Neutral',
  'Somewhat-Bearish': 'Mildly bearish',
  Bearish: 'Bearish',
};

export function NewsFeed({
  ticker,
  days = 1,
  limit = 12,
  minRelevance = 0.1,
  compact = false,
  // Ids AND titles already shown by the sentiment snapshot on the same page, so the two
  // panels never print the same headline twice. Titles matter because one wire story is
  // filed once per ticker it mentions - same headline, different id - so excluding by id
  // alone still lets a duplicate through. Over-fetch to backfill what gets filtered out.
  excludeKeys = [],
}) {
  const navigate = useNavigate();
  const clock = useMarketClock();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  // Re-fetch when the simulated DAY changes (not every clock tick).
  const simDate = clock.simulatedTime ? clock.simulatedTime.slice(0, 10) : null;
  // Unit separator: headlines routinely contain commas.
  const SEP = '\u001f';
  const excludeKey = excludeKeys.map(String).join(SEP);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listNews({
      ...(ticker ? { ticker } : {}),
      days,
      limit: limit + excludeKeys.length,
      min_relevance: minRelevance,
    })
      .then((res) => {
        if (!active) return;
        setData(res);
        setFailed(false);
      })
      .catch(() => active && setFailed(true))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // excludeKey, not excludeIds: a fresh array literal from the parent would otherwise
    // change identity every render and re-fetch in a loop.
  }, [ticker, days, limit, minRelevance, simDate, excludeKey]);

  if (loading && !data) return <div className="loading-row">Loading market news…</div>;
  if (failed) return <div className="empty-state">News feed unavailable right now.</div>;

  const excluded = new Set(excludeKey ? excludeKey.split(SEP) : []);
  const articles = (data?.articles || [])
    .filter((a) => !excluded.has(String(a.id)) && !excluded.has(a.title))
    .slice(0, limit);

  if (!articles.length) {
    return (
      <div className="empty-state">
        <span>No headlines yet for {data?.simulated_date || 'this session'}.</span>
        <span className="field-hint" style={{ marginTop: 6 }}>
          The news dataset covers 1 Jul – 31 Aug 2026. If the session clock is before that,
          an admin can move it forward under Feed &amp; Session.
        </span>
      </div>
    );
  }

  return (
    <div className="news-feed">
      <div className="news-feed-head">
        <span className="field-hint">
          Session {data.simulated_date} · {data.simulated_time} — {articles.length} headline
          {articles.length === 1 ? '' : 's'}
        </span>
      </div>

      <ul className="news-list">
        {articles.map((a) => (
          <li className="news-item" key={a.id}>
            <div className="news-item-meta">
              <span className="news-ticker font-mono">{a.ticker}</span>
              <span className={`badge badge-${TONE[a.sentiment_label] || 'neutral'}`}>
                {SHORT_LABEL[a.sentiment_label] || a.sentiment_label}
              </span>
              <span className="news-time mono-num">{String(a.published_at).slice(11, 16)}</span>
              {/* Relevance separates a story about this company from a passing mention. */}
              <span className="news-relevance" title="How much this story is about this ticker">
                rel {a.relevance_score.toFixed(2)}
              </span>
            </div>

            <p className="news-title">{a.title}</p>

            {!compact && (
              <div className="news-actions">
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => navigate('/trader/journal', { state: { citeNews: a } })}
                >
                  Journal this
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => navigate('/trader/trade', { state: { prefill: { ticker: a.ticker } } })}
                >
                  Trade {a.ticker}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
