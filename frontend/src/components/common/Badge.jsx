export function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export const kycTone = (status) => {
  if (status === 'APPROVED') return 'positive';
  if (status === 'REJECTED') return 'negative';
  return 'neutral';
};
