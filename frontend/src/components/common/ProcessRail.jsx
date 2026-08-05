import { Fragment, useEffect, useState } from 'react';
import './ProcessRail.css';

export const ORDER_STAGES = [
  { key: 'NEW', label: 'New' },
  { key: 'VALIDATED', label: 'Validated' },
  { key: 'ROUTED', label: 'Routed' },
  { key: 'FILLED', label: 'Filled' },
];

/**
 * The Process Rail — Shunryū STP's signature motif. An order really does move
 * through this exact deterministic pipeline (see OrderStatus in the backend),
 * so the stepper reflects a real sequence rather than decorating one.
 */
export function ProcessRail({ status, variant = 'compact' }) {
  if (variant === 'hero') return <HeroRail />;

  const isTerminalFail = status === 'REJECTED' || status === 'CANCELLED';
  const currentIndex = ORDER_STAGES.findIndex((s) => s.key === status);
  const activeCount = isTerminalFail ? 1 : currentIndex + 1;

  return (
    <span className={`rail rail-compact${isTerminalFail ? ' rail-failed' : ''}`} title={status || 'Unknown'}>
      {ORDER_STAGES.map((stage, i) => (
        <Fragment key={stage.key}>
          <span
            className={`rail-node${i < activeCount ? ' is-done' : ''}${isTerminalFail && i === 1 ? ' is-failed' : ''}`}
          />
          {i < ORDER_STAGES.length - 1 && (
            <span className={`rail-connector${i < activeCount - 1 ? ' is-done' : ''}${isTerminalFail && i === 0 ? ' is-failed' : ''}`} />
          )}
        </Fragment>
      ))}
      {isTerminalFail && <span className="rail-fail-label">{status}</span>}
    </span>
  );
}

function HeroRail() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setActive((prev) => (prev + 1) % (ORDER_STAGES.length + 1));
    }, 1500);
    return () => clearInterval(id);
  }, []);

  const clamped = Math.min(active, ORDER_STAGES.length - 1);
  const progress = clamped / (ORDER_STAGES.length - 1);

  return (
    <div className="rail-hero">
      <div className="rail-hero-track">
        {/* Ambient light sweep — travels the full track on a loop, independent of real
            progress, to read as a constantly-live order-flow pipeline. */}
        <div className="rail-hero-beam" />
        <div className="rail-hero-fill" style={{ width: `${progress * 100}%` }} />
        <div className="rail-hero-dot" style={{ left: `${progress * 100}%` }}>
          <span className="rail-hero-dot-ping" />
        </div>
        {ORDER_STAGES.map((stage, i) => (
          <div
            key={stage.key}
            className="rail-hero-stage"
            style={{ left: `${(i / (ORDER_STAGES.length - 1)) * 100}%` }}
          >
            <span className={`rail-node${i <= active ? ' is-done' : ''}`} />
          </div>
        ))}
      </div>
      <div className="rail-hero-labels">
        {ORDER_STAGES.map((stage, i) => (
          <span key={stage.key} className={`eyebrow${i <= active ? ' is-active' : ''}`}>
            {stage.label}
          </span>
        ))}
      </div>
    </div>
  );
}
