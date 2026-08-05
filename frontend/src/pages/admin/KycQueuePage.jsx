import { useEffect, useState } from 'react';
import { getKycQueue, getKycSubmission, approveKyc, rejectKyc } from '../../api/admin';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Card } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { Badge, kycTone } from '../../components/common/Badge';
import { formatDateTime, shortId } from '../../utils/format';
import { extractErrorMessage } from '../../api/client';
import './admin-pages.css';

const STATUS_FILTERS = ['PENDING_REVIEW', 'APPROVED', 'REJECTED'];

export function KycQueuePage() {
  const { user } = useAuth();
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState('PENDING_REVIEW');
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    getKycQueue(statusFilter)
      .then(setQueue)
      .catch(() => toast.error('Could not load the KYC queue.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [statusFilter]);

  const openDetail = (id) => {
    getKycSubmission(id)
      .then(setDetail)
      .catch(() => toast.error('Could not load this submission.'));
    setRejectReason('');
  };

  const handleApprove = async (id) => {
    setBusy(true);
    try {
      await approveKyc(id, user?.id);
      toast.success('Submission approved.');
      setDetail(null);
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not approve this submission.'));
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async (id) => {
    if (!rejectReason.trim()) {
      toast.error('Give a rejection reason first.');
      return;
    }
    setBusy(true);
    try {
      await rejectKyc(id, rejectReason.trim(), user?.id);
      toast.success('Submission rejected.');
      setDetail(null);
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not reject this submission.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>KYC Queue</h2>
          <p className="page-subtitle">Review submitted documents and unlock trading for approved traders.</p>
        </div>
        <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s.replace('_', ' ')}
            </option>
          ))}
        </select>
      </div>

      <Card>
        {loading ? (
          <div className="loading-row">Loading queue…</div>
        ) : queue.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>ID type</th>
                  <th>Auto-checks</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {queue.map((item) => (
                  <tr key={item.id}>
                    {/* The list endpoint returns account_id only; the username arrives with the detail record. */}
                    <td className="font-mono" title={item.account_id}>
                      {item.account_username || item.username || shortId(item.account_id)}
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>{item.id_type?.replace('_', ' ')}</td>
                    <td>
                      <Badge tone={item.auto_check_passed ? 'positive' : 'negative'}>
                        {item.auto_check_passed ? 'Passed' : 'Needs review'}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={kycTone(item.status)}>{item.status}</Badge>
                    </td>
                    <td>{formatDateTime(item.submitted_at)}</td>
                    <td>
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => openDetail(item.id)}>
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No submissions in this status.</div>
        )}
      </Card>

      <Modal
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        title={`Review — ${detail?.account_username || detail?.username || shortId(detail?.account_id)}`}
      >
        {detail && (
          <div className="stack" style={{ gap: 14 }}>
            <DetailRow label="Trader" value={detail.account_username || shortId(detail.account_id)} />
            <DetailRow label="ID type" value={detail.id_type?.replace('_', ' ')} />
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="eyebrow">Status</span>
              <Badge tone={kycTone(detail.status)}>{detail.status}</Badge>
            </div>
            <DetailRow label="Submitted" value={formatDateTime(detail.submitted_at)} />

            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="eyebrow">Auto-checks</span>
              <Badge tone={detail.auto_check_passed ? 'positive' : 'negative'}>
                {detail.auto_check_passed ? 'Passed' : 'Needs review'}
              </Badge>
            </div>
            {detail.auto_check_notes ? (
              <div className="ai-output" style={{ fontSize: 12 }}>
                {detail.auto_check_notes}
              </div>
            ) : null}

            <div className="eyebrow" style={{ marginTop: 4 }}>
              Extracted from document
            </div>
            <DetailRow label="Full name" value={detail.extracted_full_name} />
            <DetailRow label="Date of birth" value={detail.extracted_dob} />
            <DetailRow label="ID number" value={detail.extracted_id_number} />
            <DetailRow label="Expiry" value={detail.extracted_expiry_date} />
            <DetailRow label="Issuing country" value={detail.extracted_issuing_country} />
            <DetailRow
              label="Confidence"
              value={detail.extraction_confidence != null ? `${(detail.extraction_confidence * 100).toFixed(0)}%` : null}
            />
            {detail.document_path ? (
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span className="eyebrow">Document</span>
                <span className="font-mono" style={{ fontSize: 11, wordBreak: 'break-all', textAlign: 'right' }}>
                  {detail.document_path}
                </span>
              </div>
            ) : null}

            {detail.status === 'PENDING_REVIEW' && (
              <>
                <div className="field">
                  <label>Rejection reason (only needed to reject)</label>
                  <input className="input" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
                </div>
                <div className="row" style={{ gap: 10 }}>
                  <button className="btn btn-primary" disabled={busy} type="button" onClick={() => handleApprove(detail.id)}>
                    Approve
                  </button>
                  <button className="btn btn-danger" disabled={busy} type="button" onClick={() => handleReject(detail.id)}>
                    Reject
                  </button>
                </div>
              </>
            )}
            {detail.rejection_reason ? <div className="error-banner">{detail.rejection_reason}</div> : null}
          </div>
        )}
      </Modal>
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="row" style={{ justifyContent: 'space-between', gap: 12 }}>
      <span className="eyebrow">{label}</span>
      <span style={{ textAlign: 'right' }}>{value || '—'}</span>
    </div>
  );
}
