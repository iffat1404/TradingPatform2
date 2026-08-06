import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import './DecisionTrend.css';

/**
 * Decision quality and risk across recent trades.
 *
 * The point of the journal is improvement over time, so the trend matters more than any
 * single score. Oldest-first left to right, since that is how progress reads.
 */

const GRADE_TONE = { A: 'good', B: 'good', C: 'warn', D: 'bad' };

export function DecisionTrend({ decisions = [] }) {
  if (!decisions.length) {
    return <div className="empty-state">Place a trade to start building a decision history.</div>;
  }

  // The API returns newest-first; a trend reads better oldest-first.
  const ordered = [...decisions].reverse();
  const series = ordered.map((d, i) => ({
    label: `${d.ticker} #${i + 1}`,
    quality: d.decision_quality_score,
    risk: d.risk_score,
  }));

  const avgQuality = series.reduce((sum, d) => sum + d.quality, 0) / series.length;
  // Compare the most recent third against the earliest third to spot direction of travel.
  const window = Math.max(1, Math.floor(series.length / 3));
  const early = series.slice(0, window).reduce((s, d) => s + d.quality, 0) / window;
  const late = series.slice(-window).reduce((s, d) => s + d.quality, 0) / window;
  const drift = late - early;

  const gradeCounts = ordered.reduce((acc, d) => {
    acc[d.grade] = (acc[d.grade] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="dt-wrap">
      <div className="dt-summary">
        <div className="dt-stat">
          <span className="eyebrow">Average quality</span>
          <span className="dt-stat-value mono-num">{avgQuality.toFixed(0)}</span>
        </div>
        <div className="dt-stat">
          <span className="eyebrow">Trend</span>
          <span className={`dt-stat-value mono-num ${drift >= 0 ? 'delta-positive' : 'delta-negative'}`}>
            {drift >= 0 ? '+' : ''}
            {drift.toFixed(0)}
          </span>
        </div>
        <div className="dt-grades">
          {['A', 'B', 'C', 'D'].map((g) =>
            gradeCounts[g] ? (
              <span key={g} className={`dt-grade-pill tone-${GRADE_TONE[g]}`}>
                {g} × {gradeCounts[g]}
              </span>
            ) : null
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} minTickGap={24} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={34} />
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: 'var(--text-muted)' }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="quality" name="Decision quality" stroke="var(--positive)" strokeWidth={2} dot={{ r: 2 }} />
          <Line type="monotone" dataKey="risk" name="Risk" stroke="var(--negative)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
        </LineChart>
      </ResponsiveContainer>

      <p className="dt-note">
        {drift >= 5
          ? 'Your decision quality is improving across recent trades — the planning is sticking.'
          : drift <= -5
          ? 'Decision quality has slipped recently. Check whether targets and stops are being set.'
          : 'Decision quality is holding steady across recent trades.'}
      </p>
    </div>
  );
}
