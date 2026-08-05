import { useEffect, useRef, useState } from 'react';
import { submitKyc, getKycStatus } from '../../api/kyc';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Card } from '../../components/common/Card';
import { Badge, kycTone } from '../../components/common/Badge';
import { Field } from '../../components/common/Field';
import { Button } from '../../components/common/Button';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'application/pdf'];
const MAX_SIZE_MB = 10;

const STATUS_COPY = {
  NOT_STARTED: 'You have not submitted a KYC document yet. Trading is locked until you do.',
  PENDING_REVIEW: 'Your document is with an admin for review. This usually takes a short while in this simulation.',
  APPROVED: "You're verified — trading is unlocked.",
  REJECTED: 'Your last submission was rejected. Review the reason below and submit a new document.',
};

export function KYCPage() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState(null);
  const [idType, setIdType] = useState('passport');
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    getKycStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const validateFile = (f) => {
    if (!f) return null;
    if (!ALLOWED_TYPES.includes(f.type)) {
      toast.error('Only JPEG, PNG, or PDF files are accepted.');
      return null;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      toast.error(`File must be under ${MAX_SIZE_MB}MB.`);
      return null;
    }
    return f;
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = validateFile(e.dataTransfer.files?.[0]);
    if (f) setFile(f);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      toast.error('Choose a document to upload first.');
      return;
    }
    setSubmitting(true);
    try {
      await submitKyc(idType, file);
      toast.success('KYC document submitted for review.');
      setFile(null);
      const [s] = await Promise.all([getKycStatus(), refreshUser()]);
      setStatus(s);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not submit your document.'));
    } finally {
      setSubmitting(false);
    }
  };

  const currentStatus = status?.status || user?.kyc_status || 'NOT_STARTED';

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>KYC verification</h2>
          <p className="page-subtitle">
            A simulated, document-based check — nothing here touches a real identity registry.
          </p>
        </div>
      </div>

      <Card>
        <div className="kyc-status-card">
          <Badge tone={kycTone(currentStatus)}>{currentStatus.replace('_', ' ')}</Badge>
          <p style={{ margin: 0, fontSize: 14 }}>{STATUS_COPY[currentStatus] || STATUS_COPY.NOT_STARTED}</p>
        </div>
        {status?.rejection_reason ? <div className="error-banner" style={{ marginTop: 12 }}>{status.rejection_reason}</div> : null}
      </Card>

      {currentStatus !== 'APPROVED' && (
        <Card title="Submit a document">
          <form className="stack" style={{ gap: 16 }} onSubmit={handleSubmit}>
            <Field label="Document type">
              <select className="select" value={idType} onChange={(e) => setIdType(e.target.value)}>
                <option value="passport">Passport</option>
                <option value="drivers_license">Driver's license</option>
                <option value="national_id">National ID</option>
              </select>
            </Field>

            <div
              className={`dropzone${dragging ? ' is-dragging' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
            >
              {file ? (
                <span>{file.name}</span>
              ) : (
                <span>Drag a JPEG, PNG, or PDF here, or click to choose a file (max {MAX_SIZE_MB}MB).</span>
              )}
              <input
                ref={inputRef}
                type="file"
                accept={ALLOWED_TYPES.join(',')}
                style={{ display: 'none' }}
                onChange={(e) => setFile(validateFile(e.target.files?.[0]))}
              />
            </div>

            <Button type="submit" loading={submitting}>
              Submit for review
            </Button>
          </form>
        </Card>
      )}

      <div className="error-banner" style={{ background: 'transparent', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
        Important: this is a simulated KYC workflow for the training program. Uploaded documents are structurally
        validated only — they are never checked against a real government registry.
      </div>
    </div>
  );
}
