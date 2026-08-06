import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPortfolioSummaryAi, explainTicker, parseOrder, explainRejection } from '../../api/genai';
import { listOrders } from '../../api/orders';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Field } from '../../components/common/Field';
import { FormattedText } from '../../components/common/FormattedText';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

export function AIAssistantPage() {
  const navigate = useNavigate();
  const toast = useToast();

  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const [ticker, setTicker] = useState(TICKERS[0]);
  const [explanation, setExplanation] = useState(null);
  const [explainLoading, setExplainLoading] = useState(false);

  const [orderText, setOrderText] = useState('Buy 100 shares of AAPL at market');
  const [parsed, setParsed] = useState(null);
  const [parseLoading, setParseLoading] = useState(false);

  // Rejected orders are the most useful thing to explain — the platform's rejection codes
  // (PRICE_COLLAR_BREACH, CONCENTRATION_LIMIT_EXCEEDED...) are opaque on their own.
  const [rejected, setRejected] = useState([]);
  const [rejectedId, setRejectedId] = useState('');
  const [rejectionText, setRejectionText] = useState(null);
  const [rejectionLoading, setRejectionLoading] = useState(false);

  useEffect(() => {
    listOrders({ status: 'REJECTED' })
      .then((rows) => {
        setRejected(rows || []);
        if (rows?.length) setRejectedId(rows[0].id);
      })
      .catch(() => setRejected([]));
  }, []);

  const runSummary = () => {
    setSummaryLoading(true);
    getPortfolioSummaryAi()
      .then((res) => setSummary(res.summary))
      .catch((err) => toast.error(extractErrorMessage(err, 'AI summary is unavailable right now.')))
      .finally(() => setSummaryLoading(false));
  };

  const runExplain = () => {
    setExplainLoading(true);
    explainTicker(ticker)
      .then((res) => setExplanation(res.summary || res.explanation || null))
      .catch((err) => toast.error(extractErrorMessage(err, 'AI explanation is unavailable right now.')))
      .finally(() => setExplainLoading(false));
  };

  const runParse = () => {
    setParseLoading(true);
    parseOrder(orderText)
      .then(setParsed)
      .catch((err) => toast.error(extractErrorMessage(err, 'Could not parse that order request.')))
      .finally(() => setParseLoading(false));
  };

  // The API wraps a successful parse in `draft_order`; a failed parse returns
  // { draft_order: null, confidence: "low", error }. Handle both without assuming which.
  const draft = parsed?.draft_order || (parsed?.ticker ? parsed : null);
  const confidenceLabel =
    typeof parsed?.confidence === 'number' ? `${(parsed.confidence * 100).toFixed(0)}%` : parsed?.confidence;

  const prefillTicket = () => {
    if (!draft) return;
    // The model returns the limit as `price`; the ticket expects `limit_price`.
    navigate('/trader/trade', {
      state: { prefill: { ...draft, limit_price: draft.limit_price ?? draft.price } },
    });
  };

  const runRejection = () => {
    const order = rejected.find((o) => o.id === rejectedId);
    if (!order) return;
    setRejectionLoading(true);
    explainRejection(order.id)
      .then((res) => setRejectionText(res.explanation || res.recommendation || null))
      .catch((err) => toast.error(extractErrorMessage(err, 'Could not explain that rejection.')))
      .finally(() => setRejectionLoading(false));
  };

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>AI Assistant</h2>
          <p className="page-subtitle">
            GenAI explains and extracts — it never places or decides a trade for you. Every result below is a
            suggestion you review before acting.
          </p>
        </div>
      </div>

      <div className="two-col">
        <Card title="Portfolio summary">
          <div className="ai-tool-card">
            <p className="field-hint">Plain-language read of your current allocation and risk posture.</p>
            <Button variant="secondary" onClick={runSummary} loading={summaryLoading}>
              Generate summary
            </Button>
            {summary ? <div className="ai-output"><FormattedText>{summary}</FormattedText></div> : null}
          </div>
        </Card>

        <Card title="Explain a ticker">
          <div className="ai-tool-card">
            <Field label="Ticker">
              <select className="select" value={ticker} onChange={(e) => setTicker(e.target.value)}>
                {TICKERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
            <Button variant="secondary" onClick={runExplain} loading={explainLoading}>
              Explain {ticker}
            </Button>
            {explanation ? <div className="ai-output"><FormattedText>{explanation}</FormattedText></div> : null}
          </div>
        </Card>

        <Card title="Parse a natural-language order">
          <div className="ai-tool-card">
            <Field label="Describe the order">
              <input className="input" value={orderText} onChange={(e) => setOrderText(e.target.value)} />
            </Field>
            <Button variant="secondary" onClick={runParse} loading={parseLoading}>
              Parse order
            </Button>
            {parsed ? (
              <div className="ai-output">
                {draft ? (
                  <>
                    {draft.side?.toUpperCase()} {draft.quantity ?? draft.qty} {draft.ticker} ({draft.type})
                    {confidenceLabel ? ` — confidence ${confidenceLabel}` : ''}
                    <div style={{ marginTop: 10 }}>
                      <Button size="sm" onClick={prefillTicket}>
                        Review in Trade ticket
                      </Button>
                    </div>
                  </>
                ) : (
                  <span>{parsed.error || "Couldn't parse that into an order — try being more specific."}</span>
                )}
              </div>
            ) : null}
          </div>
        </Card>

        <Card title="Why was my order rejected?">
          <div className="ai-tool-card">
            {rejected.length ? (
              <>
                <Field label="Rejected order">
                  <select
                    className="select"
                    value={rejectedId}
                    onChange={(e) => setRejectedId(e.target.value)}
                  >
                    {rejected.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.ticker} {o.side} {o.qty ?? o.quantity} — {new Date(o.created_at).toLocaleString()}
                      </option>
                    ))}
                  </select>
                </Field>
                <Button variant="secondary" onClick={runRejection} loading={rejectionLoading}>
                  Explain this rejection
                </Button>
                {rejectionText ? (
                  <div className="ai-output">
                    <FormattedText>{rejectionText}</FormattedText>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                <span>No rejected orders — nothing to explain.</span>
                <span className="field-hint" style={{ marginTop: 6 }}>
                  If an order is ever refused (price collar, concentration limit, market
                  closed), it will appear here with a plain-language explanation.
                </span>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
