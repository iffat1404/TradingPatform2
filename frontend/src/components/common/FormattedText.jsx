import './FormattedText.css';

/**
 * Renders the light markdown models emit (headings, **bold**, bullet lists) as real
 * elements.
 *
 * Models reach for markdown regardless of what the prompt asks, and the previous plain
 * `white-space: pre-wrap` rendering showed raw `#` and `**` to the trader. This parses only
 * a safe subset and builds React nodes — no dangerouslySetInnerHTML, so model output can
 * never inject markup.
 */

// Split on **bold** while keeping the delimiters' content.
function renderInline(text, keyBase) {
  const parts = String(text).split(/(\*\*[^*]+\*\*|__[^_]+__)/g);
  return parts.filter(Boolean).map((part, i) => {
    const bold = part.match(/^\*\*([^*]+)\*\*$/) || part.match(/^__([^_]+)__$/);
    if (bold) return <strong key={`${keyBase}-b${i}`}>{bold[1]}</strong>;
    return <span key={`${keyBase}-t${i}`}>{part}</span>;
  });
}

export function FormattedText({ children, className = '' }) {
  const raw = typeof children === 'string' ? children : '';
  if (!raw.trim()) return null;

  const lines = raw.split('\n');
  const blocks = [];
  let bullets = [];

  const flushBullets = () => {
    if (!bullets.length) return;
    blocks.push(
      <ul className="ft-list" key={`ul-${blocks.length}`}>
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, `li-${blocks.length}-${i}`)}</li>
        ))}
      </ul>
    );
    bullets = [];
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (!trimmed) {
      flushBullets();
      return;
    }

    const bullet = trimmed.match(/^[-*•]\s+(.*)$/);
    if (bullet) {
      bullets.push(bullet[1]);
      return;
    }

    flushBullets();

    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      blocks.push(
        <p className="ft-heading" key={`h-${idx}`}>
          {renderInline(heading[2], `h-${idx}`)}
        </p>
      );
      return;
    }

    blocks.push(
      <p className="ft-para" key={`p-${idx}`}>
        {renderInline(trimmed, `p-${idx}`)}
      </p>
    );
  });

  flushBullets();

  return <div className={`ft ${className}`}>{blocks}</div>;
}
