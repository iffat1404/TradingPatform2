export function Button({ variant = 'primary', size, loading, className = '', children, disabled, ...props }) {
  const classes = ['btn', `btn-${variant}`, size === 'sm' ? 'btn-sm' : '', className].filter(Boolean).join(' ');
  return (
    <button className={classes} disabled={disabled || loading} {...props}>
      {loading ? 'Working…' : children}
    </button>
  );
}
