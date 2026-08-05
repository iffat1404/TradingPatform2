import { useEffect, useMemo, useRef, useState } from 'react';
import './PriceChart.css';

// Hand-rolled candlestick + volume chart, drawn straight from the backend's own OHLCV
// data — no charting SDK, no external branding, no external data source.

const MARGIN = { top: 12, right: 12, bottom: 26, left: 54 };
const VOLUME_RATIO = 0.22;
const VOLUME_GAP = 10;

function computeLayout(data, width, height) {
  if (!data?.length) return null;

  const plotHeight = Math.max(0, height - MARGIN.top - MARGIN.bottom);
  const volumeHeight = plotHeight * VOLUME_RATIO;
  const candleHeight = plotHeight - volumeHeight - VOLUME_GAP;
  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right);

  const highs = data.map((d) => d.high);
  const lows = data.map((d) => d.low);
  const priceMax = Math.max(...highs);
  const priceMin = Math.min(...lows);
  const pad = (priceMax - priceMin) * 0.08 || priceMax * 0.02 || 1;
  const yMax = priceMax + pad;
  const yMin = priceMin - pad;

  const volMax = Math.max(...data.map((d) => d.volume || 0), 1);

  const step = plotWidth / data.length;
  const candleW = Math.max(1.5, Math.min(14, step * 0.62));
  const volTop = MARGIN.top + candleHeight + VOLUME_GAP;

  const xAt = (i) => MARGIN.left + step * (i + 0.5);
  const yAt = (price) => MARGIN.top + ((yMax - price) / (yMax - yMin || 1)) * candleHeight;
  const volYAt = (vol) => volTop + volumeHeight - (vol / volMax) * volumeHeight;

  return { plotWidth, candleHeight, volumeHeight, yMax, yMin, step, candleW, volTop, xAt, yAt, volYAt };
}

export function PriceChart({ data, height = 380 }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      if (w > 0) setWidth(w);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const layout = useMemo(() => computeLayout(data, width, height), [data, width, height]);

  const handleMove = (e) => {
    if (!layout) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.round((x - MARGIN.left) / layout.step - 0.5);
    setHover(idx >= 0 && idx < data.length ? idx : null);
  };

  const gridCount = 4;
  const gridLines = layout
    ? Array.from({ length: gridCount + 1 }, (_, i) => layout.yMin + ((layout.yMax - layout.yMin) * i) / gridCount)
    : [];
  const labelEvery = layout ? Math.max(1, Math.ceil(data.length / Math.max(4, Math.floor(width / 90)))) : 1;
  const hoverPoint = layout && hover !== null ? data[hover] : null;

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height }}>
      {layout ? (
        <>
          <svg
            width={width}
            height={height}
            onMouseMove={handleMove}
            onMouseLeave={() => setHover(null)}
            style={{ display: 'block' }}
          >
            {gridLines.map((price, i) => (
              <g key={i}>
                <line
                  x1={MARGIN.left}
                  x2={width - MARGIN.right}
                  y1={layout.yAt(price)}
                  y2={layout.yAt(price)}
                  stroke="var(--border)"
                  strokeDasharray="2 4"
                />
                <text x={2} y={layout.yAt(price) + 4} fontSize="10" fill="var(--text-muted)" fontFamily="var(--font-mono)">
                  {price.toFixed(2)}
                </text>
              </g>
            ))}

            {data.map((d, i) => {
              const up = d.close >= d.open;
              const x = layout.xAt(i);
              const bodyTop = layout.yAt(Math.max(d.open, d.close));
              const bodyBottom = layout.yAt(Math.min(d.open, d.close));
              const volH = layout.volTop + layout.volumeHeight - layout.volYAt(d.volume || 0);
              return (
                <g key={i}>
                  <line
                    x1={x}
                    x2={x}
                    y1={layout.yAt(d.high)}
                    y2={layout.yAt(d.low)}
                    style={{ stroke: up ? 'var(--positive)' : 'var(--negative)' }}
                    strokeWidth={1}
                  />
                  <rect
                    x={x - layout.candleW / 2}
                    y={bodyTop}
                    width={layout.candleW}
                    height={Math.max(1, bodyBottom - bodyTop)}
                    style={{ fill: up ? 'var(--positive)' : 'var(--negative)' }}
                  />
                  <rect
                    x={x - layout.candleW / 2}
                    y={layout.volYAt(d.volume || 0)}
                    width={layout.candleW}
                    height={Math.max(1, volH)}
                    style={{ fill: up ? 'var(--positive)' : 'var(--negative)', opacity: 0.32 }}
                  />
                </g>
              );
            })}

            {hoverPoint && (
              <line
                x1={layout.xAt(hover)}
                x2={layout.xAt(hover)}
                y1={MARGIN.top}
                y2={layout.volTop + layout.volumeHeight}
                stroke="var(--text-muted)"
                strokeDasharray="3 3"
              />
            )}

            {data.map((d, i) =>
              i % labelEvery === 0 ? (
                <text
                  key={`lbl-${i}`}
                  x={layout.xAt(i)}
                  y={height - 8}
                  fontSize="10"
                  textAnchor="middle"
                  fill="var(--text-muted)"
                  fontFamily="var(--font-mono)"
                >
                  {d.label}
                </text>
              ) : null
            )}
          </svg>

          {hoverPoint && (
            <div
              className="chart-tooltip"
              style={{ left: Math.min(Math.max(0, layout.xAt(hover) + 12), width - 150) }}
            >
              <div className="eyebrow">{hoverPoint.label}</div>
              <TooltipRow label="O" value={hoverPoint.open} />
              <TooltipRow label="H" value={hoverPoint.high} />
              <TooltipRow label="L" value={hoverPoint.low} />
              <TooltipRow label="C" value={hoverPoint.close} />
              <div className="chart-tooltip-row">
                <span>Vol</span>
                <span className="mono-num">{Math.round(hoverPoint.volume || 0).toLocaleString()}</span>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="empty-state" style={{ position: 'absolute', inset: 0 }}>
          No price data for this range yet.
        </div>
      )}
    </div>
  );
}

function TooltipRow({ label, value }) {
  return (
    <div className="chart-tooltip-row">
      <span>{label}</span>
      <span className="mono-num">{value?.toFixed?.(2) ?? '—'}</span>
    </div>
  );
}
