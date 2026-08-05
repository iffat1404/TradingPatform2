import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export function PriceMaChart({ data, height = 240 }) {
  if (!data?.length) return <div className="empty-state">No indicator history for this ticker yet.</div>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} minTickGap={40} />
        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={54} />
        <Tooltip
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
        />
        <Line type="monotone" dataKey="close" stroke="var(--text)" strokeWidth={1.5} dot={false} name="Close" />
        <Line type="monotone" dataKey="sma20" stroke="var(--positive)" strokeWidth={1.5} dot={false} name="SMA 20" />
        <Line type="monotone" dataKey="sma50" stroke="var(--info)" strokeWidth={1.5} dot={false} name="SMA 50" />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RsiGauge({ value }) {
  if (value === null || value === undefined) return <div className="empty-state">No RSI data.</div>;
  const pct = Math.max(0, Math.min(100, value));
  const tone = value >= 70 || value <= 30 ? 'var(--negative)' : 'var(--positive)';
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span className="eyebrow">RSI (14)</span>
        <span className="mono-num" style={{ color: tone, fontWeight: 600 }}>
          {value.toFixed(1)}
        </span>
      </div>
      <div style={{ position: 'relative', height: 8, borderRadius: 999, background: 'var(--border)', overflow: 'hidden' }}>
        <div
          style={{
            position: 'absolute',
            left: '30%',
            width: '40%',
            top: 0,
            bottom: 0,
            background: 'color-mix(in srgb, var(--positive) 20%, transparent)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: `${pct}%`,
            top: -2,
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: tone,
            transform: 'translateX(-50%)',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span className="field-hint">Oversold</span>
        <span className="field-hint">Overbought</span>
      </div>
    </div>
  );
}

export function MacdPanel({ macd }) {
  if (!macd) return <div className="empty-state">No MACD data.</div>;
  const histogram = Array.isArray(macd.histogram)
    ? macd.histogram.map((v, i) => ({ i, v: typeof v === 'number' ? v : v?.value ?? 0 }))
    : null;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="eyebrow">MACD</span>
        <span className="mono-num">{macd.macd?.toFixed?.(3) ?? '—'}</span>
      </div>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="eyebrow">Signal</span>
        <span className="mono-num">{macd.signal?.toFixed?.(3) ?? '—'}</span>
      </div>
      {histogram?.length ? (
        <ResponsiveContainer width="100%" height={80}>
          <BarChart data={histogram}>
            <XAxis dataKey="i" hide />
            <Bar dataKey="v">
              {histogram.map((row) => (
                <Cell key={row.i} fill={row.v >= 0 ? 'var(--positive)' : 'var(--negative)'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : null}
    </div>
  );
}

export function BollingerPanel({ bands }) {
  if (!bands) return <div className="empty-state">No Bollinger Band data.</div>;
  return (
    <div className="stat-row">
      <div className="stat-card">
        <span className="stat-label">Upper</span>
        <span className="stat-value">{bands.upper?.toFixed?.(2) ?? '—'}</span>
      </div>
      <div className="stat-card">
        <span className="stat-label">Middle</span>
        <span className="stat-value">{bands.middle?.toFixed?.(2) ?? '—'}</span>
      </div>
      <div className="stat-card">
        <span className="stat-label">Lower</span>
        <span className="stat-value">{bands.lower?.toFixed?.(2) ?? '—'}</span>
      </div>
    </div>
  );
}
