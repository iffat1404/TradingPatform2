export const formatCurrency = (value, { decimals = 2 } = {}) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = value < 0 ? '-' : '';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
};

export const formatNumber = (value, decimals = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

export const formatPercent = (value, decimals = 2) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
};

export const formatDateTime = (value) => {
  if (!value) return '—';
  try {
    const d = new Date(value.endsWith?.('Z') || value.includes?.('+') ? value : `${value}Z`);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return value;
  }
};

export const formatTime = (value) => {
  if (!value) return '—';
  try {
    const d = new Date(value.endsWith?.('Z') || value.includes?.('+') ? value : `${value}Z`);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  } catch {
    return value;
  }
};

// OrderResponse declares `qty` with alias "quantity", and FastAPI serializes by alias —
// so the wire field is `quantity` while some paths still emit `qty`. Accept either.
export const orderQty = (order) => order?.qty ?? order?.quantity ?? '—';

// Account ids are UUIDs; show a short prefix in dense admin tables.
export const shortId = (id) => (typeof id === 'string' && id.length > 10 ? `${id.slice(0, 8)}…` : id || '—');

export const deltaClass = (value) => {
  if (value > 0) return 'delta-positive';
  if (value < 0) return 'delta-negative';
  return 'delta-neutral';
};
