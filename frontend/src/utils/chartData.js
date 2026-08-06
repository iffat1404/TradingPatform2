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
// suffix. The backend returns timestamps that are already in UTC, but as strings.
// We parse them as UTC explicitly by appending 'Z'.
export const toIntradayPoints = (rows = []) =>
  rows.map((r) => {
    // Backend returns timestamp as "YYYY-MM-DD HH:MM:SS" string
    // Treat it as UTC by appending Z
    const iso = `${r.timestamp.replace(' ', 'T')}Z`;
    const timestamp = new Date(iso).getTime();

    // Store the full original timestamp string for display
    const fullTimestamp = r.timestamp; // e.g., "2026-07-01 09:31:00"

    return {
      label: fullTimestamp,
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

// Intraday data covers a fixed simulated window (Jul 1 - Aug 30).
// For intraday chart, return all data for the current trading day (full day scroll available),
// not just data up to "now". This allows users to scroll left/right through full day data.
export const filterToSimulatedDay = (points, simulatedTimeIso) => {
  if (!simulatedTimeIso) return [];
  const dayKey = simulatedTimeIso.slice(0, 10);
  return points.filter((p) => p.dateKey === dayKey);
};
