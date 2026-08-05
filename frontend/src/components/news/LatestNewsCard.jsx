import { useEffect, useState } from 'react';
import './LatestNewsCard.css';

export function LatestNewsCard() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const fetchNews = async () => {
      try {
        // Fetch news for the primary tickers (AAPL, MSFT, NVDA, GOOGL)
        const tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL'];
        const results = [];

        for (const ticker of tickers) {
          const res = await fetch(`/api/news/${ticker}/recent?limit=3`);
          if (res.ok) {
            const articles = await res.json();
            results.push(...articles);
          }
        }

        if (active) {
          // Sort by published_at DESC and limit to 6
          results.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
          setNews(results.slice(0, 6));
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
  }, []);

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
    const now = new Date();
    const diffMs = now - date;
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
    <div className="news-list">
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
              <span className="news-source">{article.source}</span>
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


