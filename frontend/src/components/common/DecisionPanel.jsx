import { useState } from 'react';
import { FormattedText } from './FormattedText';
import './DecisionPanel.css';

/**
 * Decision Intelligence readout.
 *
 * Shows the two deterministic scores and, on demand, the full factor breakdown that
 * produced them. Advisory only — nothing here can block an order.
 */

const GRADE_TONE = { A: 'good', B: 'good', C: 'warn', D: 'bad' };

// Risk is inverted: a high risk score is the bad end of the scale.
const riskTone = (score) => (score >= 70 ? 'bad' : score >= 45 ? 'warn' : 'good');
const qualityTone = (score) => (score >= 65 ? 'good' : score >= 45 ? 'warn' : 'bad');

function Gauge({ label, score, tone, hint }) {
  return (
    <div className="di-gauge">
      <div className="di-gauge-head">
        <span className="eyebrow">{label}</span>
        <span className={`di-gauge-value tone-${tone}`}>{Math.round(score)}</span>
      </div>
      <div className="di-gauge-track" role="img" aria-label={`${label}: ${Math.round(score)} out of 100`}>
        <div className={`di-gauge-fill tone-${tone}`} style={{ width: `${Math.max(2, Math.min(100, score))}%` }} />
      </div>
      <span className="di-gauge-hint">{hint}</span>
    </div>
  );
}

function FactorRow({ factor, invert }) {
  const tone = invert ? riskTone(factor.score) : qualityTone(factor.score);
  return (
    <li className="di-factor">
      <div className="di-factor-head">
        <span className="di-factor-label">{factor.label}</span>
        <span className="di-factor-meta">
          <span className="di-factor-weight">{Math.round(factor.weight * 100)}%</span>
          <span className={`di-factor-score tone-${tone}`}>{Math.round(factor.score)}</span>
        </span>
      </div>
      <div className="di-factor-track">
        <div className={`di-factor-fill tone-${tone}`} style={{ width: `${Math.max(2, Math.min(100, factor.score))}%` }} />
      </div>
      <p className="di-factor-note">{factor.note}</p>
    </li>
  );
}

export function DecisionPanel({ decision, loading, error, compact = false }) {
  const [open, setOpen] = useState(false);

  if (loading && !decision) {
    return <div className="loading-row">Scoring this decision…</div>;
  }
  if (error) {
    return <div className="di-muted">Decision scoring unavailable right now.</div>;
  }
  if (!decision) {
    return <div className="di-muted">Enter a quantity to score this decision.</div>;
  }

  const { risk_score: risk, decision_quality_score: quality, grade } = decision;

  return (
    <div className={`di-panel${loading ? ' is-refreshing' : ''}`}>
      <div className="di-header">
        <span className="eyebrow">Decision intelligence</span>
        <span className={`di-grade tone-${GRADE_TONE[grade] || 'warn'}`} title="Decision quality grade">
          {grade}
        </span>
      </div>

      <Gauge label="Risk" score={risk} tone={riskTone(risk)} hint="Higher means more risk taken on." />
      <Gauge
        label="Decision quality"
        score={quality}
        tone={qualityTone(quality)}
        hint="Higher means a better-planned trade."
      />

      {decision.explanation?.explanation ? (
        <div className="di-coaching"><FormattedText>{decision.explanation.explanation}</FormattedText></div>
      ) : null}

      {!compact && (
        <>
          <button className="di-toggle" type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? 'Hide' : 'Why this score?'}
          </button>

          {open && (
            <div className="di-breakdown">
              <span className="eyebrow di-breakdown-title">What drives the risk</span>
              <ul className="di-factor-list">
                {(decision.risk_factors || []).map((f) => (
                  <FactorRow key={f.key} factor={f} invert />
                ))}
              </ul>

              <span className="eyebrow di-breakdown-title">What drives the quality</span>
              <ul className="di-factor-list">
                {(decision.quality_factors || []).map((f) => (
                  <FactorRow key={f.key} factor={f} />
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <p className="di-disclaimer">
        Advisory only — this scores your decision process, never which stock to trade, and
        never blocks an order.
      </p>
    </div>
  );
}
