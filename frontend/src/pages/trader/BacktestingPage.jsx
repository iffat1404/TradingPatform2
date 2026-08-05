import { useEffect, useState } from 'react';
import { createStrategy, listStrategies, listBacktestRuns, runBacktest, getBacktestResults } from '../../api/paperTrading';
import { Card } from '../../components/common/Card';
import { Field } from '../../components/common/Field';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { useToast } from '../../context/ToastContext';
import { formatDateTime, formatPercent, formatCurrency } from '../../utils/format';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

const todayIso = () => new Date().toISOString().slice(0, 10);

export function BacktestingPage() {
  const [tab, setTab] = useState('strategies');
  const [strategies, setStrategies] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: '', description: '', shortPeriod: 20, longPeriod: 50 });
  const [creating, setCreating] = useState(false);
  const [runForm, setRunForm] = useState({ strategyId: '', start: todayIso(), end: todayIso() });
  const [running, setRunning] = useState(false);
  const [activeResult, setActiveResult] = useState(null);
  const toast = useToast();

  const load = () => {
    setLoading(true);
    Promise.all([listStrategies(), listBacktestRuns()])
      .then(([s, r]) => {
        setStrategies(s);
        setRuns(r);
      })
      .catch(() => toast.error('Could not load backtesting data.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createStrategy({
        name: form.name,
        description: form.description,
        parameters: { short_term_period: Number(form.shortPeriod), long_term_period: Number(form.longPeriod) },
      });
      toast.success('Strategy created.');
      setForm({ name: '', description: '', shortPeriod: 20, longPeriod: 50 });
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not create strategy.'));
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (e) => {
    e.preventDefault();
    if (!runForm.strategyId) return;
    setRunning(true);
    try {
      await runBacktest(runForm.strategyId, { start_date: runForm.start, end_date: runForm.end });
      toast.success('Backtest started.');
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not run backtest.'));
    } finally {
      setRunning(false);
    }
  };

  const openResults = (runId) => {
    getBacktestResults(runId)
      .then(setActiveResult)
      .catch(() => toast.error('Could not load backtest results.'));
  };

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Backtesting</h2>
          <p className="page-subtitle">Isolated from your live portfolio — build a strategy, run it, review it.</p>
        </div>
      </div>

      <div className="chart-range-tabs">
        <button className={tab === 'strategies' ? 'is-active' : ''} onClick={() => setTab('strategies')} type="button">
          Strategies
        </button>
        <button className={tab === 'runs' ? 'is-active' : ''} onClick={() => setTab('runs')} type="button">
          Backtests
        </button>
      </div>

      {tab === 'strategies' && (
        <div className="two-col">
          <Card title="New strategy">
            <form className="stack" style={{ gap: 14 }} onSubmit={handleCreate}>
              <Field label="Name">
                <input className="input" required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
              </Field>
              <Field label="Description">
                <input className="input" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
              </Field>
              <div className="form-grid">
                <Field label="Short MA period">
                  <input
                    className="input"
                    type="number"
                    min={1}
                    value={form.shortPeriod}
                    onChange={(e) => setForm((f) => ({ ...f, shortPeriod: e.target.value }))}
                  />
                </Field>
                <Field label="Long MA period">
                  <input
                    className="input"
                    type="number"
                    min={1}
                    value={form.longPeriod}
                    onChange={(e) => setForm((f) => ({ ...f, longPeriod: e.target.value }))}
                  />
                </Field>
              </div>
              <Button type="submit" loading={creating}>
                Create strategy
              </Button>
            </form>
          </Card>

          <Card title="Your strategies">
            {loading ? (
              <div className="loading-row">Loading…</div>
            ) : strategies.length ? (
              <ul className="stack" style={{ gap: 10 }}>
                {strategies.map((s) => (
                  <li key={s.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
                    <strong>{s.name}</strong>
                    <p className="field-hint" style={{ margin: '2px 0 0' }}>
                      {s.description || 'No description'}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">No strategies yet.</div>
            )}
          </Card>
        </div>
      )}

      {tab === 'runs' && (
        <div className="page-section">
          <Card title="Run a backtest">
            <form className="filters-row" onSubmit={handleRun}>
              <div className="field">
                <label>Strategy</label>
                <select className="select" value={runForm.strategyId} onChange={(e) => setRunForm((f) => ({ ...f, strategyId: e.target.value }))}>
                  <option value="">Select a strategy</option>
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Start date</label>
                <input className="input" type="date" value={runForm.start} onChange={(e) => setRunForm((f) => ({ ...f, start: e.target.value }))} />
              </div>
              <div className="field">
                <label>End date</label>
                <input className="input" type="date" value={runForm.end} onChange={(e) => setRunForm((f) => ({ ...f, end: e.target.value }))} />
              </div>
              <Button type="submit" loading={running} disabled={!runForm.strategyId}>
                Run backtest
              </Button>
            </form>
          </Card>

          <Card title="Backtest history">
            {runs.length ? (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Total return</th>
                      <th>Sharpe</th>
                      <th>Created</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.id}>
                        <td style={{ textTransform: 'capitalize' }}>{r.status}</td>
                        <td className={`mono-num ${r.total_return >= 0 ? 'delta-positive' : 'delta-negative'}`}>
                          {formatPercent((r.total_return || 0) * 100)}
                        </td>
                        <td className="mono-num">{r.sharpe_ratio?.toFixed?.(2) ?? '—'}</td>
                        <td>{formatDateTime(r.created_at)}</td>
                        <td>
                          <button className="btn btn-ghost btn-sm" type="button" onClick={() => openResults(r.id)}>
                            View results
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">No backtests run yet.</div>
            )}
          </Card>
        </div>
      )}

      <Modal open={Boolean(activeResult)} onClose={() => setActiveResult(null)} title="Backtest results">
        {activeResult && (
          <div className="stack" style={{ gap: 12 }}>
            <div className="stat-row">
              <StatCardInline label="Final capital" value={formatCurrency(activeResult.final_capital)} />
              <StatCardInline label="Total return" value={formatPercent((activeResult.total_return || 0) * 100)} />
              <StatCardInline label="Sharpe" value={activeResult.sharpe_ratio?.toFixed?.(2) ?? '—'} />
              <StatCardInline label="Max drawdown" value={formatPercent((activeResult.max_drawdown || 0) * 100)} />
              <StatCardInline label="Trades" value={activeResult.total_trades ?? '—'} />
              <StatCardInline label="Win rate" value={formatPercent((activeResult.win_rate || 0) * 100)} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function StatCardInline({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}
