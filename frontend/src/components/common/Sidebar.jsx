import { NavLink } from 'react-router-dom';
import { Icon } from './Icon';
import './Sidebar.css';

export function Sidebar({ items, roleLabel, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-mark">N</span>
        <div>
          <div className="sidebar-brand-name">NOMURA STP</div>
          <div className="sidebar-brand-role">{roleLabel}</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `sidebar-link${isActive ? ' is-active' : ''}`}
          >
            <Icon name={item.icon} size={17} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <button className="sidebar-logout" onClick={onLogout} type="button">
        <Icon name="logout" size={17} />
        <span>Log out</span>
      </button>
    </aside>
  );
}
