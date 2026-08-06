import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  getJournalTags,
  listJournalEntries,
  createJournalEntry,
  updateJournalEntry,
  deleteJournalEntry,
  analyzeJournalEntry,
  getJournalInsights,
  reviewEntryNews,
} from '../../api/journal';
import { listOrders } from '../../api/orders';
import { listNews } from '../../api/news';
import { getDecisionHistory } from '../../api/decision';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { StatCard } from '../../components/common/StatCard';
import { Button } from '../../components/common/Button';
import { Field } from '../../components/common/Field';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { FormattedText } from '../../components/common/FormattedText';
import { DecisionTrend } from '../../components/common/DecisionTrend';
import { useToast } from '../../context/ToastContext';
import { formatDateTime, orderQty } from '../../utils/format';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

// Tags that indicate elevated behavioural risk get the negative tone; the rest read neutral
// or positive. Keeps the chip colour meaningful rather than decorative.
const RISK_TAGS = new Set(['fomo', 'revenge', 'greedy', 'fearful', 'anxious', 'frustrated']);
const GOOD_TAGS = new Set(['confident', 'disciplined']);

const NEWS_TONE = {
  Bullish: 'positive',
  'Somewhat-Bullish': 'positive',
  Neutral: 'neutral',
  'Somewhat-Bearish': 'negative',
  Bearish: 'negative',
};

// A verdict is about whether the news matched the move, not whether the trade made money.
const VERDICT_TONE = {
  confirmed: 'positive',
  contradicted: 'negative',
  flat: 'neutral',
  no_signal: 'neutral',
  unknown: 'neutral',
};

const VERDICT_LABEL = {
  confirmed: 'News played out',
  contradicted: 'News did NOT play out',
  flat: 'Price barely moved',
  no_signal: 'Neutral story, price moved anyway',
  unknown: 'Not yet measurable',
};

const tagTone = (tag) => (RISK_TAGS.has(tag) ? 'negative' : GOOD_TAGS.has(tag) ? 'positive' : 'neutral');

const FLAG_LABELS = {
  possible_fomo: 'Possible FOMO',
  possible_revenge_trade: 'Possible revenge trade',
  elevated_stress: 'Elevated stress',
  size_discipline_risk: 'Size discipline risk',
  losing_trade_review: 'Losing trade — review process',
};

export function JournalPage() {
  const toast = useToast();
  const [tags, setTags] = useState([]);
  const [entries, setEntries] = useState([]);
  const [orders, setOrders] = useState([]);
  const [insights, setInsights] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [newsOptions, setNewsOptions] = useState([]);
  const [reviews, setReviews] = useState({});      // entryId -> news review
  const [reviewingId, setReviewingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(false);

  const [form, setForm] = useState({ orderId: '', ticker: '', rationale: '', tags: [], newsId: '' });
  const [submitting, setSubmitting] = useState(false);

  const [filterTicker, setFilterTicker] = useState('');
  const [filterTag, setFilterTag] = useState('');

  const [analyzingId, setAnalyzingId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({ rationale: '', tags: [] });
  const [savingEdit, setSavingEdit] = useState(false);

  const loadEntries = () => {
    const params = {};
    if (filterTicker) params.ticker = filterTicker;
    if (filterTag) params.emotional_tag = filterTag;
    return listJournalEntries(params)
      .then(setEntries)
      .catch(() => toast.error('Could not load your journal entries.'));
  };

  const loadInsights = (announce = false) => {
    setInsightsLoading(true);
    return getJournalInsights()
      .then((res) => {
        setInsights(res);
        if (announce) toast.success('Insights refreshed.');
      })
      .catch(() => setInsights(null))
      .finally(() => setInsightsLoading(false));
  };

  useEffect(() => {
    Promise.all([
      getJournalTags().then((r) => setTags(r.tags || [])).catch(() => setTags([])),
      listOrders({ status: 'FILLED' }).then(setOrders).catch(() => setOrders([])),
      getDecisionHistory(30).then(setDecisions).catch(() => setDecisions([])),
      // Headlines the trader could plausibly be citing today.
      listNews({ days: 2, limit: 40, min_relevance: 0.3 })
        .then((r) => setNewsOptions(r.articles || []))
        .catch(() => setNewsOptions([])),
      loadEntries(),
      loadInsights(),
    ]).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterTicker, filterTag]);

  // Arriving from the news feed's "Journal this" button.
  const location = useLocation();
  useEffect(() => {
    const cited = location.state?.citeNews;
    if (!cited) return;
    setNewsOptions((prev) => (prev.some((a) => a.id === cited.id) ? prev : [cited, ...prev]));
    setForm((f) => ({ ...f, newsId: cited.id, ticker: cited.ticker }));
  }, [location.state]);

  const toggleTag = (tag, current, setter) => {
    setter(current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.rationale.trim()) {
      toast.error('Write your rationale before saving.');
      return;
    }
    setSubmitting(true);
    try {
      await createJournalEntry({
        order_id: form.orderId || null,
        ticker: form.orderId ? null : form.ticker || null,
        entry_type: form.orderId ? 'trade_note' : 'reflection',
        rationale: form.rationale.trim(),
        emotional_tags: form.tags,
        news_article_id: form.newsId || null,
      });
      toast.success('Journal entry saved.');
      setForm({ orderId: '', ticker: '', rationale: '', tags: [], newsId: '' });
      await Promise.all([loadEntries(), loadInsights()]);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not save your entry.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAnalyze = async (entry, regenerate = false) => {
    setAnalyzingId(entry.id);
    try {
      const res = await analyzeJournalEntry(entry.id, regenerate);
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entry.id
            ? { ...e, ai_feedback: res.feedback, ai_flags: res.flags || [], ai_generated_by: res.generated_by }
            : e
        )
      );
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not generate feedback.'));
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleNewsReview = async (entry) => {
    setReviewingId(entry.id);
    try {
      const res = await reviewEntryNews(entry.id);
      setReviews((prev) => ({ ...prev, [entry.id]: res }));
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not review this news thesis.'));
    } finally {
      setReviewingId(null);
    }
  };

  const openEdit = (entry) => {
    setEditing(entry);
    setEditForm({ rationale: entry.rationale || '', tags: entry.emotional_tags || [] });
  };

  const handleSaveEdit = async () => {
    if (!editForm.rationale.trim()) {
      toast.error('Rationale cannot be empty.');
      return;
    }
    setSavingEdit(true);
    try {
      await updateJournalEntry(editing.id, {
        rationale: editForm.rationale.trim(),
        emotional_tags: editForm.tags,
      });
      toast.success('Entry updated.');
      setEditing(null);
      await Promise.all([loadEntries(), loadInsights()]);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not update the entry.'));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDelete = async (entry) => {
    try {
      await deleteJournalEntry(entry.id);
      toast.info('Entry deleted.');
      await Promise.all([loadEntries(), loadInsights()]);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not delete the entry.'));
    }
  };

  const topTag = useMemo(() => {
    const counts = insights?.tag_counts || {};
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted.length ? `${sorted[0][0]} (${sorted[0][1]})` : '—';
  }, [insights]);

  if (loading) return <div className="loading-row">Loading your journal…</div>;

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Trading journal</h2>
          <p className="page-subtitle">
            Log why you took a trade and how you felt. Patterns are detected from your real order
            history — the AI coach only explains what the rules already found.
          </p>
        </div>
      </div>

      {/* ---- AI Coach ---- */}
      <Card
        title="AI coach"
        action={
          <Button variant="secondary" size="sm" onClick={() => loadInsights(true)} loading={insightsLoading}>
            Refresh insights
          </Button>
        }
      >
        <div className="stat-row" style={{ marginBottom: 16 }}>
          <StatCard label="Entries logged" value={insights?.entry_count ?? 0} />
          <StatCard label="Filled trades" value={insights?.filled_order_count ?? 0} />
          <StatCard label="Journaled coverage" value={`${insights?.journaled_coverage_pct ?? 0}%`} />
          <StatCard label="Unjournaled trades" value={insights?.unjournaled_trade_count ?? 0} />
          <StatCard label="Top emotion" value={topTag} />
        </div>

        {insights?.narrative ? (
          <div className="ai-output">
            <FormattedText>{insights.narrative}</FormattedText>
            <div className="journal-provenance">
              {insights.generated_by && !['deterministic', 'error'].includes(insights.generated_by)
                ? `Written by ${insights.generated_by} from your rule-detected patterns.`
                : 'Rule-based summary — AI narration unavailable, so the underlying analysis is shown directly.'}
            </div>
          </div>
        ) : (
          <div className="empty-state">No insights yet — log your first entry to get started.</div>
        )}

        {insights?.findings?.length ? (
          <div className="journal-findings">
            {insights.findings.map((f) => (
              <div className="journal-finding" key={f.flag}>
                <div className="journal-finding-head">
                  <Badge tone="negative">{f.label}</Badge>
                  <span className="mono-num">{f.count}</span>
                </div>
                <p>{f.detail}</p>
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      {/* ---- Decision quality over time ---- */}
      {decisions.length ? (
        <Card title="Decision quality over time">
          <DecisionTrend decisions={decisions} />
        </Card>
      ) : null}

      {/* ---- Composer ---- */}
      <Card title="New entry">
        <form className="stack" style={{ gap: 16 }} onSubmit={handleSubmit}>
          <div className="form-grid">
            <Field label="Link to a filled trade" hint="Leave blank to log a standalone reflection">
              <select
                className="select"
                value={form.orderId}
                onChange={(e) => setForm((f) => ({ ...f, orderId: e.target.value }))}
              >
                <option value="">No linked trade (reflection)</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.ticker} · {o.side} {orderQty(o)} · {formatDateTime(o.created_at)}
                  </option>
                ))}
              </select>
            </Field>

            {/* Available for any entry — a trade note or a standalone reflection can both
                be driven by a headline, and citing it is what makes the thesis reviewable. */}
            <Field
              label="Which headline drove this?"
              hint="Optional — lets the coach check whether that news actually moved the price"
            >
              <select
                className="select"
                value={form.newsId}
                onChange={(e) => setForm((f) => ({ ...f, newsId: e.target.value }))}
              >
                <option value="">No specific headline</option>
                {newsOptions.map((a) => (
                  <option key={a.id} value={a.id}>
                    [{a.ticker}] {a.title.slice(0, 70)}
                  </option>
                ))}
              </select>
            </Field>

            {!form.orderId && (
              <Field label="Ticker (optional)">
                <select
                  className="select"
                  value={form.ticker}
                  onChange={(e) => setForm((f) => ({ ...f, ticker: e.target.value }))}
                >
                  <option value="">No specific ticker</option>
                  {TICKERS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>

          <Field label="Rationale">
            <textarea
              className="input journal-textarea"
              rows={4}
              placeholder="What was the setup? What made you act — or hold off?"
              value={form.rationale}
              onChange={(e) => setForm((f) => ({ ...f, rationale: e.target.value }))}
            />
          </Field>

          <Field label="How did you feel?" hint="Be honest — this is what makes the pattern detection work">
            <div className="tag-chip-row">
              {tags.map((tag) => (
                <button
                  type="button"
                  key={tag}
                  className={`tag-chip${form.tags.includes(tag) ? ' is-selected' : ''} tone-${tagTone(tag)}`}
                  onClick={() => toggleTag(tag, form.tags, (next) => setForm((f) => ({ ...f, tags: next })))}
                >
                  {tag}
                </button>
              ))}
            </div>
          </Field>

          <Button type="submit" loading={submitting}>
            Save entry
          </Button>
        </form>
      </Card>

      {/* ---- Filters ---- */}
      <div className="filters-row">
        <div className="field">
          <label>Ticker</label>
          <select className="select" value={filterTicker} onChange={(e) => setFilterTicker(e.target.value)}>
            <option value="">All</option>
            {TICKERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Emotion</label>
          <select className="select" value={filterTag} onChange={(e) => setFilterTag(e.target.value)}>
            <option value="">All</option>
            {tags.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        {(filterTicker || filterTag) && (
          <Button
            variant="ghost"
            onClick={() => {
              setFilterTicker('');
              setFilterTag('');
            }}
          >
            Clear filters
          </Button>
        )}
      </div>

      {/* ---- Timeline ---- */}
      {entries.length ? (
        <div className="journal-timeline">
          {entries.map((entry) => (
            <div className="journal-entry-card" key={entry.id}>
              <div className="journal-entry-head">
                <div className="journal-entry-meta">
                  {entry.order ? (
                    <span className="journal-trade-chip">
                      <span className="font-mono">{entry.order.ticker}</span>
                      <Badge tone={entry.order.side === 'buy' ? 'positive' : 'negative'}>{entry.order.side}</Badge>
                      <span className="mono-num">{orderQty(entry.order)}</span>
                    </span>
                  ) : (
                    <span className="journal-trade-chip">
                      <Badge tone="neutral">Reflection</Badge>
                      {entry.ticker ? <span className="font-mono">{entry.ticker}</span> : null}
                    </span>
                  )}
                  {entry.is_auto ? (
                    <span className="journal-auto-chip" title="Logged automatically when this trade filled">
                      Auto-logged
                    </span>
                  ) : null}
                  <span className="field-hint">{formatDateTime(entry.created_at)}</span>
                </div>
                <div className="journal-entry-actions">
                  <button className="btn btn-ghost btn-sm" type="button" onClick={() => openEdit(entry)}>
                    {entry.needs_annotation ? 'Add reasoning' : 'Edit'}
                  </button>
                  <button className="btn btn-danger btn-sm" type="button" onClick={() => handleDelete(entry)}>
                    Delete
                  </button>
                </div>
              </div>

              {entry.needs_annotation ? (
                <button className="journal-annotate-prompt" type="button" onClick={() => openEdit(entry)}>
                  This trade was logged for you. Add why you took it — the coach can only
                  spot patterns in reasoning you have written down.
                </button>
              ) : (
                <p className="journal-rationale">{entry.rationale}</p>
              )}

              {entry.emotional_tags?.length ? (
                <div className="tag-chip-row">
                  {entry.emotional_tags.map((tag) => (
                    <span key={tag} className={`tag-chip is-static tone-${tagTone(tag)}`}>
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}

              {entry.ai_feedback ? (
                <div className="ai-output" style={{ marginTop: 12 }}>
                  <span className="eyebrow">Coach feedback</span>
                  <FormattedText>{entry.ai_feedback}</FormattedText>
                  {entry.ai_flags?.length ? (
                    <div className="tag-chip-row" style={{ marginTop: 10 }}>
                      {entry.ai_flags.map((flag) => (
                        <Badge key={flag} tone="negative">
                          {FLAG_LABELS[flag] || flag}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                  {/* Say plainly whether a model wrote this or a rule did — otherwise a
                      quota-exhausted provider looks identical to working AI. */}
                  <div className="journal-provenance">
                    {entry.ai_generated_by && !['deterministic', 'error'].includes(entry.ai_generated_by)
                      ? `Written by ${entry.ai_generated_by}.`
                      : 'Rule-based feedback — the AI provider was unavailable, so the underlying analysis is shown directly.'}
                  </div>
                  <div className="journal-entry-actions" style={{ marginTop: 10 }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      type="button"
                      disabled={analyzingId === entry.id}
                      onClick={() => handleAnalyze(entry, true)}
                    >
                      {analyzingId === entry.id ? 'Regenerating…' : 'Regenerate'}
                    </button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  style={{ marginTop: 12 }}
                  loading={analyzingId === entry.id}
                  onClick={() => handleAnalyze(entry)}
                >
                  Get AI feedback
                </Button>
              )}

              {/* The headline this entry says drove the trade, plus the thesis review. */}
              {entry.news_article ? (
                <div className="journal-news" style={{ marginTop: 12 }}>
                  <div className="journal-news-head">
                    <span className="eyebrow">Traded on this news</span>
                    <Badge tone={NEWS_TONE[entry.news_article.sentiment_label] || 'neutral'}>
                      {entry.news_article.sentiment_label}
                    </Badge>
                    <span className="news-relevance">rel {entry.news_article.relevance_score}</span>
                  </div>
                  <p className="journal-news-title">{entry.news_article.title}</p>

                  {reviews[entry.id] ? (
                    <NewsReview review={reviews[entry.id]} />
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={reviewingId === entry.id}
                      onClick={() => handleNewsReview(entry)}
                    >
                      Did this news actually move it?
                    </Button>
                  )}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <Card>
          <div className="empty-state">
            {filterTicker || filterTag
              ? 'No entries match these filters.'
              : 'No journal entries yet. Log your first one above.'}
          </div>
        </Card>
      )}

      {/* ---- Edit modal ---- */}
      <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Edit entry">
        {editing && (
          <div className="stack" style={{ gap: 16 }}>
            <Field label="Rationale">
              <textarea
                className="input journal-textarea"
                rows={4}
                value={editForm.rationale}
                onChange={(e) => setEditForm((f) => ({ ...f, rationale: e.target.value }))}
              />
            </Field>
            <Field label="How did you feel?">
              <div className="tag-chip-row">
                {tags.map((tag) => (
                  <button
                    type="button"
                    key={tag}
                    className={`tag-chip${editForm.tags.includes(tag) ? ' is-selected' : ''} tone-${tagTone(tag)}`}
                    onClick={() => toggleTag(tag, editForm.tags, (next) => setEditForm((f) => ({ ...f, tags: next })))}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </Field>
            <Button onClick={handleSaveEdit} loading={savingEdit}>
              Save changes
            </Button>
          </div>
        )}
      </Modal>
    </div>
  );
}

/**
 * The deterministic verdict on a news thesis, plus what the trader overlooked.
 * The numbers here are computed server-side; the coaching sentence is the only AI part.
 */
function NewsReview({ review }) {
  const r = review?.review;
  if (!r) return null;

  return (
    <div className="journal-news-review">
      <div className="journal-news-head">
        <Badge tone={VERDICT_TONE[r.verdict] || 'neutral'}>
          {VERDICT_LABEL[r.verdict] || r.verdict}
        </Badge>
        {r.actual_move_pct !== null && r.actual_move_pct !== undefined ? (
          <span className={`mono-num ${r.actual_move_pct >= 0 ? 'delta-positive' : 'delta-negative'}`}>
            {r.actual_move_pct >= 0 ? '+' : ''}
            {r.actual_move_pct}%
          </span>
        ) : null}
        {r.measured_to ? <span className="news-relevance">to {r.measured_to}</span> : null}
      </div>

      <p className="journal-news-verdict">{r.verdict_text}</p>

      {r.missed?.length ? (
        <div className="journal-news-missed">
          <span className="eyebrow">
            What you did not mention ({r.same_day_article_count} other stories that day)
          </span>
          <ul>
            {r.missed.map((m) => (
              <li key={m.title}>
                <Badge tone={NEWS_TONE[m.sentiment_label] || 'neutral'}>{m.sentiment_label}</Badge>
                <span className="journal-news-missed-title">{m.title}</span>
                <span className="field-hint"> — {m.why}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {review.coaching ? (
        <div className="ai-output" style={{ marginTop: 10 }}>
          <span className="eyebrow">Coach</span>
          <FormattedText>{review.coaching}</FormattedText>
          <div className="journal-provenance">
            {review.generated_by && !['deterministic', 'error'].includes(review.generated_by)
              ? `Written by ${review.generated_by} from the computed verdict above.`
              : 'Rule-based summary of the computed verdict above.'}
          </div>
        </div>
      ) : null}
    </div>
  );
}
