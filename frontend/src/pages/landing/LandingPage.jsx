import { Link } from 'react-router-dom';
import { motion, MotionConfig } from 'framer-motion';
import { ProcessRail } from '../../components/common/ProcessRail';
import { TickerTape } from '../../components/common/TickerTape';
import { Icon } from '../../components/common/Icon';
import './landing.css';

const FEATURES = [
  {
    icon: 'markets',
    title: 'Real-time markets',
    body: 'Seven live instruments on a deterministic simulated feed, synchronized to a single global MarketClock for every trader in the room.',
  },
  {
    icon: 'compliance',
    title: 'Risk controls, by the book',
    body: 'Price collars, notional caps, concentration limits, and wash-trade detection run on every order — before it ever reaches the book.',
  },
  {
    icon: 'analytics',
    title: 'Real analytics',
    body: 'SMA, EMA, RSI, MACD, and Bollinger Bands, with alerts and sentiment-divergence checks against real news data.',
  },
  {
    icon: 'backtest',
    title: 'Paper-trading backtests',
    body: 'Build a strategy, run it against historical data, and see the results — completely isolated from your live portfolio.',
  },
];

const TICKER_NAMES = {
  AAPL: 'Apple Inc.',
  GOOG: 'Alphabet Inc.',
  IBM: 'IBM Corp.',
  MSFT: 'Microsoft Corp.',
  TSLA: 'Tesla Inc.',
  UL: 'Unilever PLC',
  WMT: 'Walmart Inc.',
};

const EASE = [0.16, 1, 0.3, 1];

const heroContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.05 } },
};

const heroItem = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE } },
};

const cardContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const cardItem = {
  hidden: { opacity: 0, y: 26 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
};

const MotionLink = motion.create(Link);

export function LandingPage() {
  return (
    <MotionConfig reducedMotion="user">
      <div className="theme-light landing">
        <nav className="landing-nav">
          <div className="landing-brand">
            <span className="landing-mark">N</span>
            <span className="font-mono landing-brand-name">SHUNRYŪ STP</span>
          </div>
          <div className="landing-nav-links">
            <a href="#process">Product</a>
            <a href="#markets">Markets</a>
            <a href="#features">Features</a>
          </div>
          <div className="landing-nav-actions">
            <Link to="/login" className="btn btn-ghost btn-sm">
              Sign in
            </Link>
            <Link to="/register" className="btn btn-primary btn-sm">
              Start trading
            </Link>
          </div>
        </nav>

        <motion.header
          className="landing-hero container"
          initial="hidden"
          animate="show"
          variants={heroContainer}
        >
          <motion.span className="eyebrow" variants={heroItem}>
            Straight-through processing, simulated
          </motion.span>
          <motion.h1 className="font-display landing-headline" variants={heroItem}>
            Trade smarter.
            <br />
            Trade straight-through.
          </motion.h1>
          <motion.p className="landing-subcopy" variants={heroItem}>
            Shunryū STP is a paper-trading platform built on the same discipline as a real
            order-management system: every order moves through a deterministic pipeline,
            validated and audited, with zero manual intervention — and $1,000,000 in virtual
            capital to practice with.
          </motion.p>
          <motion.div className="landing-cta-row" variants={heroItem}>
            <MotionLink
              to="/register"
              className="btn btn-primary btn-glow"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.97 }}
            >
              <span>Start trading</span>
              <span className="btn-arrow" aria-hidden="true">
                →
              </span>
            </MotionLink>
            <motion.a
              href="#process"
              className="btn btn-secondary"
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              See how STP works
            </motion.a>
          </motion.div>

          <motion.div id="process" className="landing-rail-block" variants={heroItem}>
            <ProcessRail variant="hero" />
          </motion.div>
        </motion.header>

        <TickerTape />

        <section id="features" className="landing-features container">
          <span className="eyebrow">Why traders choose Shunryū STP</span>
          <h2 className="font-display landing-section-title">Built like a real desk, sized for learning</h2>
          <motion.div
            className="landing-feature-grid"
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.25 }}
            variants={cardContainer}
          >
            {FEATURES.map((f) => (
              <motion.div
                className="landing-feature-card"
                key={f.title}
                variants={cardItem}
                whileHover={{ y: -6 }}
                transition={{ type: 'spring', stiffness: 300, damping: 22 }}
              >
                <div className="landing-feature-icon">
                  <Icon name={f.icon} size={20} />
                </div>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </motion.div>
            ))}
          </motion.div>
        </section>

        <section id="markets" className="landing-markets container">
          <motion.div
            className="landing-markets-card"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7, ease: EASE }}
          >
            <div className="landing-markets-mesh" aria-hidden="true">
              <span className="mesh-blob mesh-blob-a" />
              <span className="mesh-blob mesh-blob-b" />
              <span className="mesh-blob mesh-blob-c" />
            </div>

            <div className="landing-markets-content">
              <span className="eyebrow">Tradable instruments</span>
              <h2 className="font-display landing-section-title">Seven names. One deterministic tape.</h2>
              <p className="landing-subcopy">
                Trade against a synthetic feed replayed at 1×, 2×, 5×, 12×, or 30× speed by
                your admin — so a full trading day can fit inside a single class session.
              </p>

              <div className="ticker-pill-row">
                {Object.keys(TICKER_NAMES).map((t) => (
                  <span className="ticker-pill-badge" key={t} data-tip={TICKER_NAMES[t]} tabIndex={0}>
                    {t}
                  </span>
                ))}
              </div>

              <Link to="/register" className="btn btn-primary">
                Create a trader account
              </Link>
            </div>
          </motion.div>
        </section>

        <footer className="landing-footer">
          <div className="container landing-footer-inner">
            <div>
              <div className="landing-brand">
                <span className="landing-mark">N</span>
                <span className="font-mono landing-brand-name">SHUNRYŪ STP</span>
              </div>
              <p className="landing-footer-note">
                For the Shunryū Tech Graduate Program. Simulated markets, simulated KYC — no real
                funds, no real trades.
              </p>
            </div>
            <div className="landing-footer-links">
              <Link to="/login">Sign in</Link>
              <Link to="/register">Start trading</Link>
            </div>
          </div>
        </footer>
      </div>
    </MotionConfig>
  );
}
