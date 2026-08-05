export function Card({ title, action, children, className = '' }) {
  return (
    <div className={`card ${className}`}>
      {(title || action) && (
        <div className="card-title">
          <span>{title}</span>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
