import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { extractErrorMessage } from '../../api/client';
import { Field } from '../../components/common/Field';
import { Button } from '../../components/common/Button';
import './auth.css';

export function RegisterPage() {
  const { register, isAuthenticated, role, initializing } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '', confirm: '', startingCapital: 1000000 });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!initializing && isAuthenticated) {
      navigate(role === 'admin' ? '/admin/overview' : '/trader/overview', { replace: true });
    }
  }, [initializing, isAuthenticated, role, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    try {
      await register({
        username: form.username.trim(),
        password: form.password,
        starting_capital: Number(form.startingCapital) || 1000000,
      });
      navigate('/trader/overview', { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not create your account.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="theme-light auth-shell">
      <aside className="auth-side">
        <div className="auth-side-top landing-brand">
          <span className="auth-side-mark">N</span>
          <span className="font-mono landing-brand-name">SHUNRYŪ STP</span>
        </div>
        <p className="auth-side-quote">
          $1,000,000 in virtual capital. Seven live instruments. Zero real risk — every rule
          still applies.
        </p>
        <span className="eyebrow" style={{ color: 'var(--ink-300)' }}>
          Trader accounts only — admin access is provisioned separately
        </span>
      </aside>

      <main className="auth-main">
        <div className="auth-card">
          <div>
            <h1>Create your account</h1>
            <p className="auth-card-subtitle">Trader access — you'll complete KYC before your first order.</p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error ? <div className="error-banner">{error}</div> : null}
            <Field label="Username" hint="3–20 characters">
              <input
                className="input"
                type="text"
                required
                minLength={3}
                maxLength={20}
                autoFocus
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              />
            </Field>
            <Field label="Password" hint="At least 8 characters">
              <input
                className="input"
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </Field>
            <Field label="Confirm password">
              <input
                className="input"
                type="password"
                required
                value={form.confirm}
                onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
              />
            </Field>
            <Field label="Starting capital" hint="Defaults to $1,000,000 — for classroom scenarios you can adjust it">
              <input
                className="input"
                type="number"
                min={0}
                step={1000}
                value={form.startingCapital}
                onChange={(e) => setForm((f) => ({ ...f, startingCapital: e.target.value }))}
              />
            </Field>
            <Button type="submit" loading={loading} style={{ width: '100%' }}>
              Create account
            </Button>
          </form>

          <p className="auth-footer-note">
            Already trading? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
