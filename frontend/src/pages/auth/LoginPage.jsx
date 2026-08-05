import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { extractErrorMessage } from '../../api/client';
import { Field } from '../../components/common/Field';
import { Button } from '../../components/common/Button';
import { ORDER_STAGES } from '../../components/common/ProcessRail';
import './auth.css';

export function LoginPage() {
  const { login, isAuthenticated, role, initializing } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '' });
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
    setLoading(true);
    try {
      const me = await login(form.username.trim(), form.password);
      navigate(me.role === 'admin' ? '/admin/overview' : '/trader/overview', { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not sign in — check your username and password.'));
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
        <div className="auth-side-rail">
          <p className="auth-side-quote">
            "Every order takes the same path — validated, routed, filled. Nothing skips the
            line."
          </p>
          <div className="auth-side-rail-track">
            {ORDER_STAGES.map((stage, i) => (
              <span key={stage.key} className={i === 2 ? 'is-current' : ''}>
                {stage.label}
              </span>
            ))}
          </div>
        </div>
        <span className="eyebrow" style={{ color: 'var(--ink-300)' }}>
          Shunryū Tech Graduate Program
        </span>
      </aside>

      <main className="auth-main">
        <div className="auth-card">
          <div>
            <h1>Sign in</h1>
            <p className="auth-card-subtitle">Trade, review, or supervise — pick up where you left off.</p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error ? <div className="error-banner">{error}</div> : null}
            <Field label="Username">
              <input
                className="input"
                type="text"
                required
                autoFocus
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              />
            </Field>
            <Field label="Password">
              <input
                className="input"
                type="password"
                required
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </Field>
            <Button type="submit" loading={loading} style={{ width: '100%' }}>
              Sign in
            </Button>
          </form>

          <p className="auth-footer-note">
            New here? <Link to="/register">Create a trader account</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
