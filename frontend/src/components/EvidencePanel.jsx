import React, { useRef, useState } from 'react';
import FormattedText from './FormattedText';
import { sourceDomain } from './SourceLedger';

const SOURCE_LABELS = { technology: 'Technology', hiring: 'Hiring', web_search: 'Web search', fundamentals_error: 'Company fundamentals', news_error: 'Recent news' };

const SIGNAL_LABELS = {
  funding_stage: 'Funding stage',
  total_funding: 'Total funding',
  headcount: 'Headcount',
  headcount_range: 'Headcount range',
  founded_year: 'Founded',
  headquarters: 'Headquarters',
  revenue_estimate: 'Revenue estimate',
};

function SignalGrid({ signals }) {
  const rows = Object.entries(SIGNAL_LABELS)
    .filter(([key]) => signals?.[key] && signals[key] !== 'Unknown')
    .map(([key, label]) => ({ label, value: signals[key] }));

  if (!rows.length) return <p className="muted">No structured signals extracted.</p>;

  return (
    <dl className="kv">
      {rows.map(({ label, value }) => (
        <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
      ))}
    </dl>
  );
}

// Raw search text can run long; show the first part and let the reader expand the rest.
const COLLAPSED_CHARS = 1200;

function CollapsibleText({ text }) {
  const [showAll, setShowAll] = useState(false);
  const long = String(text || '').length > COLLAPSED_CHARS;
  return (
    <>
      <div className={long && !showAll ? 'evidence-collapsed' : undefined}>
        <FormattedText text={text} />
      </div>
      {long && (
        <button type="button" className="evidence-toggle" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>
          {showAll ? 'Show less' : 'Show all'}
        </button>
      )}
    </>
  );
}

const TABS = [
  { id: 'company_signals', title: 'Company', type: 'structured', urls: 'web_search' },
  { id: 'web_search', title: 'Fundamentals & news', type: 'text', urls: 'web_search' },
  { id: 'technology', title: 'Technology', type: 'text', urls: 'technology' },
  { id: 'hiring', title: 'Hiring', type: 'text', urls: 'hiring' },
];

function EvidencePanel({ evidence }) {
  const [selected, setSelected] = useState(TABS[0].id);
  const tabRefs = useRef({});
  // Same numbers the verdict cites, so a [n] in the verdict can be found here.
  const sourceIds = Object.fromEntries((evidence?.sources || []).map((source) => [source.url, source.id]));
  const failures = Object.keys({ ...(evidence?.source_errors || {}), ...(evidence?.partial_errors || {}) });
  const tab = TABS.find(({ id }) => id === selected);
  const urls = evidence?.source_urls?.[tab.urls] || [];

  // Arrow keys move between tabs (WAI-ARIA tabs pattern).
  const onKeyDown = (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    const index = (TABS.findIndex(({ id }) => id === selected) + step + TABS.length) % TABS.length;
    setSelected(TABS[index].id);
    tabRefs.current[TABS[index].id]?.focus();
  };

  return (
    <section className="block" aria-labelledby="evidence-title">
      <div className="block-head"><h2 id="evidence-title">Evidence</h2><span className="mono">raw research</span></div>
      {failures.map((source) => (
        <p key={source} role="alert" className="alert">
          {SOURCE_LABELS[source] || source} couldn&apos;t be retrieved, so the verdict rests on the other sources.
        </p>
      ))}
      <div className="tabs" role="tablist" aria-label="Evidence sources" onKeyDown={onKeyDown}>
        {TABS.map(({ id, title }) => (
          <button
            key={id}
            ref={(node) => { tabRefs.current[id] = node; }}
            type="button"
            role="tab"
            id={`tab-${id}`}
            className="tab"
            aria-selected={selected === id}
            aria-controls={`panel-${id}`}
            tabIndex={selected === id ? 0 : -1}
            onClick={() => setSelected(id)}
          >
            {title}
          </button>
        ))}
      </div>
      <div className="tab-panel" role="tabpanel" id={`panel-${tab.id}`} aria-labelledby={`tab-${tab.id}`}>
        {!evidence?.[tab.id] ? (
          <p className="muted">No data available.</p>
        ) : tab.type === 'structured' ? (
          <SignalGrid signals={evidence[tab.id]} />
        ) : (
          <CollapsibleText key={tab.id} text={evidence[tab.id]} />
        )}
        {urls.length > 0 && (
          <div className="source-chips">
            {urls.map((url) => (
              <a key={url} href={url} target="_blank" rel="noreferrer" title={url}>
                {sourceIds[url] && <b>{sourceIds[url]} </b>}{sourceDomain(url)}
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export default EvidencePanel;
