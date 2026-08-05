const PATHS = {
  overview: 'M3 3h7v7H3V3Zm11 0h7v4h-7V3ZM3 14h7v7H3v-7Zm11-3h7v10h-7V11Z',
  markets: 'M3 17l5-6 4 3 6-8 3 3M3 20h18',
  trade: 'M4 15l5-6 4 4 7-9M4 4v16h16',
  portfolio: 'M4 7h16v13H4V7Zm4-4h8v4H8V3Z',
  orders: 'M5 4h14v16H5V4Zm3 5h8m-8 4h8m-8 4h5',
  analytics: 'M4 20V10m6 10V4m6 16v-7m6 7V8',
  backtest: 'M12 3a9 9 0 1 0 9 9M12 3v6l5 3',
  ai: 'M12 3v3m0 12v3m9-9h-3M6 12H3m14.5-6.5-2 2M8.5 15.5l-2 2m0-11 2 2m6 6 2 2M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
  kyc: 'M5 3h14v18l-7-4-7 4V3Zm3 6h8m-8 4h5',
  journal: 'M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm0 0v18M9 8h7M9 12h7M9 16h4',
  settings:
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm8 4-1.8.4a6.6 6.6 0 0 0-.6-1.5l1.1-1.5-1.5-1.5-1.5 1.1a6.6 6.6 0 0 0-1.5-.6L14 4h-2l-.4 1.8a6.6 6.6 0 0 0-1.5.6L8.6 5.3 7.1 6.8l1.1 1.5a6.6 6.6 0 0 0-.6 1.5L4 12l1.6.4a6.6 6.6 0 0 0 .6 1.5l-1.1 1.5 1.5 1.5 1.5-1.1a6.6 6.6 0 0 0 1.5.6L10 20h2l.4-1.6a6.6 6.6 0 0 0 1.5-.6l1.5 1.1 1.5-1.5-1.1-1.5a6.6 6.6 0 0 0 .6-1.5L20 12Z',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m6 14 5-5-5-5m5 5H9',
  'kyc-queue': 'M4 6h16M4 12h10M4 18h7m9-6h.01',
  accounts: 'M17 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2m10-14a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm7 6v6m3-3h-6',
  audit: 'M9 3h9v16l-4.5-3L9 19V3Zm-5 4h2m-2 4h2m-2 4h2',
  compliance: 'M12 2 4 5v6c0 5 3.4 8.7 8 11 4.6-2.3 8-6 8-11V5l-8-3Zm-2 10 2 2 4-4',
  feed: 'M4 19V5m5 14v-9m5 9v-5m5 5V7',
  bell: 'M6 8a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6Zm4 10a2 2 0 0 0 4 0',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm10 17-5.5-5.5',
  close: 'M6 6l12 12M18 6 6 18',
  chevronRight: 'M9 6l6 6-6 6',
  upload: 'M12 16V4m0 0L7 9m5-5 5 5M5 20h14',
  download: 'M12 4v12m0 0-5-5m5 5 5-5M5 20h14',
};

export function Icon({ name, size = 18, className = '' }) {
  const d = PATHS[name];
  if (!d) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}
