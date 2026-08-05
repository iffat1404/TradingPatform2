import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPortfolioSummaryAi, explainTicker, parseOrder, extractId } from '../../api/genai';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Field } from '../../components/common/Field';
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

  const [noteText, setNoteText] = useState('');
  const [extracted, setExtracted] = useState(null);
  const [extractLoading, setExtractLoading] = useState(false);

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
      .then((res) => setExplanation(res.explanation))
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
    navigate('/trader/trade', { state: { prefill: draft } });
  };

  const runExtract = () => {
    setExtractLoading(true);
    extractId(noteText)
      .then(setExtracted)
      .catch((err) => toast.error(extractErrorMessage(err, 'Could not extract an identifier from that text.')))
      .finally(() => setExtractLoading(false));
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
            {summary ? <div className="ai-output">{summary}</div> : null}
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
            {explanation ? <div className="ai-output">{explanation}</div> : null}
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

        <Card title="Extract an identifier">
          <div className="ai-tool-card">
            <Field label="Paste a note or message">
              <input
                className="input"
                placeholder="e.g. account ACC123 flagged for XYZ activity"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
              />
            </Field>
            <Button variant="secondary" onClick={runExtract} loading={extractLoading} disabled={!noteText.trim()}>
              Extract
            </Button>
            {extracted ? (
              <div className="ai-output">
                Account: {extracted.account_id || '—'} · Ticker: {extracted.ticker || '—'}
                {extracted.confidence !== undefined ? ` · Confidence ${(extracted.confidence * 100).toFixed(0)}%` : ''}
              </div>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}
