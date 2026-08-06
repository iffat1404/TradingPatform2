import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNewsStream } from '../../hooks/useNewsStream';
import './NewsAlert.css';

export function NewsAlert() {
  const [hasNewNews, setHasNewNews] = useState(false);
  const [showPopup, setShowPopup] = useState(false);
  const navigate = useNavigate();

  // Subscribe to global news stream
  useNewsStream((data) => {
    if (data.articles && data.articles.length > 0) {
      setHasNewNews(true);
    }
  });

  const handleGoToOverview = () => {
    navigate('/trader/overview');
    setShowPopup(false);
    setHasNewNews(false);
  };

  if (!hasNewNews) return null;

  return (
    <>
      <button
        className="news-alert-badge"
        onClick={() => setShowPopup(true)}
        aria-label="New news available"
      >
        📰 New News
      </button>

      {showPopup && (
        <div className="news-popup-overlay" onClick={() => setShowPopup(false)}>
          <div className="news-popup-content" onClick={(e) => e.stopPropagation()}>
            <button className="popup-close" onClick={() => setShowPopup(false)}>
              ✕
            </button>

            <div className="popup-icon">📰</div>
            <h3 className="popup-title">New News Available</h3>
            <p className="popup-message">New news items have arrived. Check the Overview page to see all today's news.</p>

            <button className="popup-action-btn" onClick={handleGoToOverview}>
              Go to Overview →
            </button>
          </div>
        </div>
      )}
    </>
  );
}

