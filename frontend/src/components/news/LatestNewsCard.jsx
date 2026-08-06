import { useEffect, useState } from 'react';
import { listNews } from '../../api/news';
import './LatestNewsCard.css';

/**
 * A sentiment snapshot: the few stories carrying the strongest read on the market right now.
 *
 * Deliberately a different cut from the "Market news" feed alongside it, which is
 * chronological and relevance-filtered. This one ranks by sentiment strength and reports the
 * ids it used via `onFeatured`, so the full feed can drop them and the two panels never show
 * the same headline twice.
 */
export function LatestNewsCard({ limit = 3, onFeatured }) {
  const [news, setNews] = useState([]);
  // "Now" has to come from the simulation, not the browser. Ageing a 2026 headline against
  // the real wall clock reports every story as months old.
  const [simulatedNow, setSimulatedNow] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const fetchNews = async () => {
      try {
        // One call through apiClient: it carries the auth token and the configured API host.
        // A bare relative fetch() hit the Vite dev server instead and 404'd on every request.
        // The backend already orders newest-first and refuses to return future news.
        const res = await listNews({ days: 3, limit: 30 });
        if (!active) return;
        // Strongest signal first — a Bullish 0.4 says more than a Neutral 0.02. Ties break
        // to the newer story.
        const ranked = [...(res.articles || [])]
          .sort(
            (a, b) =>
              Math.abs(b.sentiment_score) - Math.abs(a.sentiment_score) ||
              new Date(b.published_at) - new Date(a.published_at)
          )
          .slice(0, limit);
        setNews(ranked);
        if (res.simulated_date && res.simulated_time) {
          setSimulatedNow(new Date(`${res.simulated_date}T${res.simulated_time}`));
        }
      } catch (err) {
        console.error('Error fetching news:', err);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchNews();
    // Refresh every 60 seconds
    const interval = setInterval(fetchNews, 60000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [limit]);

  // Report which headlines this panel claimed. Keyed on the joined ids so a 60s refresh that
  // returns the same stories doesn't churn the parent.
  const SEP = '\u001f';
  const featuredKey = [...news.map((a) => String(a.id)), ...news.map((a) => a.title)].join(SEP);
  useEffect(() => {
    if (onFeatured) onFeatured(featuredKey ? featuredKey.split(SEP) : []);
  }, [featuredKey, onFeatured]);

  const getSentimentIcon = (label) => {
    if (label === 'Bullish' || label === 'Somewhat-Bullish') return '📈';
    if (label === 'Bearish' || label === 'Somewhat-Bearish') return '📉';
    return '➡️';
  };

  const getSentimentColor = (label) => {
    if (label === 'Bullish' || label === 'Somewhat-Bullish') return '#51a958';
    if (label === 'Bearish' || label === 'Somewhat-Bearish') return '#ea3d3d';
    return '#6d6a6a';
  };

  const formatTime = (isoString) => {
    const date = new Date(isoString);
    const now = simulatedNow || new Date();
    const diffMs = now - date;
    if (diffMs < 0) return 'just now';
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return <div className="loading-row">Loading latest news…</div>;
  }

  return (
    <div className="latest-news">
      {news.length ? (
        news.map((article) => (
          <div key={article.id} className="news-item">
            <div className="news-header">
              <span className="font-mono news-ticker">{article.ticker}</span>
              <div className="sentiment-info">
                <span
                  className="sentiment-badge"
                  style={{ color: getSentimentColor(article.sentiment_label) }}
                >
                  {getSentimentIcon(article.sentiment_label)} {article.sentiment_label}
                </span>
                <span className="sentiment-score">
                  {(article.sentiment_score * 100).toFixed(1)}%
                </span>
              </div>
            </div>
            <p className="news-title">{article.title}</p>
            <div className="news-footer">
              {/* The feed has no publisher field; the lead topic is the useful label here. */}
              <span className="news-source">{article.topics?.[0] || article.date}</span>
              <span className="news-time">{formatTime(article.published_at)}</span>
            </div>
          </div>
        ))
      ) : (
        <div className="empty-state">No recent news items available.</div>
      )}
    </div>
  );
}


