import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Icon } from './Icon';
import './Sidebar.css';

export function Sidebar({ items, roleLabel, onLogout, isCollapsed, onToggle, onHoverChange }) {
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseEnter = () => {
    setIsHovered(true);
    onHoverChange?.(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    onHoverChange?.(false);
  };

  return (
    <aside 
      className={`sidebar ${isCollapsed ? 'is-collapsed' : ''} ${isCollapsed && isHovered ? 'is-hovered' : ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="sidebar-brand">
        <span className="sidebar-mark">N</span>
        <div>
          <div className="sidebar-brand-name">SHUNRYŪ STP</div>
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
      {/* <button 
        className="sidebar-toggle" 
        onClick={onToggle}
        type="button"
        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        <div className="sidebar-toggle-icon">
          {isCollapsed ? (
            <>
              <span className="sidebar-toggle-line sidebar-toggle-line-2"></span>
              <span className="sidebar-toggle-line sidebar-toggle-line-1"></span>
            </>
          ) : (
            <>
              <span className="sidebar-toggle-line sidebar-toggle-line-1"></span>
              <span className="sidebar-toggle-line sidebar-toggle-line-2"></span>
            </>
          )}
        </div>
      </button> */}
    </aside>
  );
}
