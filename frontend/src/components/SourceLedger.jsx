import React from 'react';

export function sourceDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function sourcePath(url) {
  try {
    const { pathname } = new URL(url);
    return pathname === '/' ? '' : decodeURIComponent(pathname).replace(/\/$/, '');
  } catch {
    return '';
  }
}

// Numbered in this order by the pipeline, so the ledger reads 1..n top to bottom.
const GROUP_ORDER = ['technology', 'hiring', 'web search'];
const GROUP_LABELS = { 'web search': 'Company & news', technology: 'Technology', hiring: 'Hiring' };

// Every numbered source the verdict can cite. Hovering a row highlights the matching [n] in the verdict.
function SourceLedger({ sources, hotId, onHover }) {
  if (!sources?.length) return null;
  const groups = GROUP_ORDER
    .map((group) => ({ group, items: sources.filter((source) => source.group === group) }))
    .filter(({ items }) => items.length);

  return (
    <section aria-labelledby="ledger-title">
      <h2 id="ledger-title" className="ledger-title">Sources <span className="mono">{sources.length}</span></h2>
      {groups.map(({ group, items }) => (
        <div key={group} className="ledger-group">
          <h3>{GROUP_LABELS[group] || group}</h3>
          <ol className="ledger-list">
            {items.map((source) => (
              <li key={source.id}>
                <a
                  id={`source-${source.id}`}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className={hotId === source.id ? 'is-hot' : undefined}
                  onMouseEnter={() => onHover(source.id)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(source.id)}
                  onBlur={() => onHover(null)}
                >
                  <span className="ledger-id">{String(source.id).padStart(2, '0')}</span>
                  <span>
                    <span className="ledger-domain">{sourceDomain(source.url)}</span>
                    {sourcePath(source.url) && <span className="ledger-path">{sourcePath(source.url)}</span>}
                  </span>
                </a>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}

export default SourceLedger;
