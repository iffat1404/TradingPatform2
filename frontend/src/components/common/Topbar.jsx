import { MarketPulse } from './MarketPulse';
import { Icon } from './Icon';
import './Topbar.css';

export function Topbar({ title, user, notificationCount = 0 }) {
  return (
    <header className="topbar">
      <h1 className="topbar-title">{title}</h1>
      <div className="topbar-actions">
        <MarketPulse />
        <button className="topbar-icon-btn" type="button" aria-label="Notifications">
          <Icon name="bell" size={18} />
          {notificationCount > 0 ? <span className="topbar-badge">{notificationCount}</span> : null}
        </button>
        <div className="topbar-user">
          <div className="topbar-avatar">{user?.username?.[0]?.toUpperCase() || '?'}</div>
          <div className="topbar-user-meta">
            <span className="topbar-username">{user?.username}</span>
            <span className="topbar-role">{user?.role}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
