export function StatCard({ label, value, delta, deltaTone }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className={`stat-value${!delta && deltaTone ? ` ${deltaTone}` : ''}`}>{value}</span>
      {delta ? <span className={`stat-delta ${deltaTone || ''}`}>{delta}</span> : null}
    </div>
  );
}
