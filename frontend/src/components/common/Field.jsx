export function Field({ label, hint, error, children }) {
  return (
    <div className="field">
      {label ? <label>{label}</label> : null}
      {children}
      {error ? <span className="field-error">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}
