// Daily bars come as { date: "2026-07-01", ... } — one point per trading day.
export const toDailyPoints = (rows = []) =>
  rows.map((r) => {
    const timestamp = new Date(`${r.date}T00:00:00Z`).getTime();
    return {
      label: r.date,
      dateKey: r.date,
      t: timestamp,
      timestamp,
      open: r.open,
      high: r.high,
      low: r.low,
      close: r.close,
      volume: r.volume,
    };
  });

// Intraday bars come as { timestamp: "2026-07-01 09:31:00", ... } — minute-level, no timezone
// suffix, always UTC per the backend's own convention.
export const toIntradayPoints = (rows = []) =>
  rows.map((r) => {
    const iso = `${r.timestamp.replace(' ', 'T')}Z`;
    const timestamp = new Date(iso).getTime();
    return {
      label: r.timestamp.slice(11, 16),
      dateKey: r.timestamp.slice(0, 10),
      t: timestamp,
      timestamp,
      open: r.open,
      high: r.high,
      low: r.low,
      close: r.close,
      volume: r.volume,
    };
  });

// Intraday data covers a fixed simulated window (Jul 1 - Aug 30). A trader should only ever
// see bars up to "now" on the MarketClock, and only for the current simulated trading day —
// never the full multi-week dataset at once.
export const filterToSimulatedDay = (points, simulatedTimeIso) => {
  if (!simulatedTimeIso) return [];
  const now = new Date(simulatedTimeIso).getTime();
  const dayKey = simulatedTimeIso.slice(0, 10);
  return points.filter((p) => p.dateKey === dayKey && p.t <= now);
};
