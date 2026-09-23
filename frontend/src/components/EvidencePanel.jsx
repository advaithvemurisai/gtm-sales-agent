import React, { useState } from 'react';
import FormattedText from './FormattedText';

const SOURCE_LABELS = { technology: 'Technology signals', hiring: 'Hiring signals', web_search: 'Web search' };

function sourceDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

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

  if (!rows.length) {
    return <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>No structured signals extracted.</p>;
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {rows.map(({ label, value }) => (
        <div key={label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '0.9rem 1rem', borderRadius: 8, background: 'rgba(255, 255, 255, 0.02)' }}>
          <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{label}</span>
          <span style={{ fontSize: 13, color: 'var(--color-text-primary)', fontWeight: 500, textAlign: 'right' }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

const SECTIONS = [
  { id: 'company_signals', title: 'Company Signals', icon: 'ti-chart-infographic', type: 'structured' },
  { id: 'web_search', title: 'Web Search', icon: 'ti-world-search', type: 'text' },
  { id: 'technology', title: 'Technology Signals', icon: 'ti-stack-2', type: 'text' },
  { id: 'hiring', title: 'Hiring Signals', icon: 'ti-users', type: 'text' },
];

function EvidencePanel({ evidence }) {
  const [expanded, setExpanded] = useState('company_signals');
  const toggle = (id) => setExpanded(expanded === id ? null : id);

  return (
    <div style={{ marginTop: '1.75rem', maxWidth: 760, margin: '1.75rem auto 0' }}>
      <div style={{ marginBottom: '0.8rem' }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>
          Supporting evidence
        </p>
        <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', lineHeight: 1.6, margin: 0 }}>
          Expand any section to review the most relevant signals behind the verdict.
        </p>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        {Object.entries(evidence?.source_errors || {}).map(([source]) => (
          <div key={source} role="alert" style={{ padding: '12px 14px', border: '1px solid rgba(210, 153, 34, 0.35)', background: 'rgba(210, 153, 34, 0.08)', borderRadius: 8, color: '#d29922', fontSize: 13 }}>
            {SOURCE_LABELS[source] || source}: couldn't be retrieved, so the verdict is based on the other sources.
          </div>
        ))}
        {SECTIONS.map(({ id, title, icon, type }) => {
          const isOpen = expanded === id;
          const hasData = evidence && (type === 'structured' ? evidence[id] : evidence[id]);

          return (
            <div key={id} style={{ border: '1px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', background: 'var(--color-background-secondary)', overflow: 'hidden' }}>
              <button
                onClick={() => toggle(id)}
                style={{ width: '100%', padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(255, 255, 255, 0.04)', display: 'grid', placeItems: 'center' }}>
                    <i className={`ti ${icon}`} style={{ fontSize: 12, color: 'var(--color-text-secondary)' }} />
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)' }}>{title}</span>
                </div>
                <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>{isOpen ? 'Close' : 'Open'}</span>
              </button>

              {isOpen && (
                <div style={{ padding: '1rem 1rem 1.1rem', background: 'rgba(255, 255, 255, 0.02)' }}>
                  {!hasData ? (
                    <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: 0 }}>No data available.</p>
                  ) : type === 'structured' ? (
                    <SignalGrid signals={evidence[id]} />
                  ) : (
                    <FormattedText text={evidence[id]} />
                  )}
                  {(evidence?.source_urls?.[id] || []).length > 0 && (
                    <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {evidence.source_urls[id].map((url) => <a key={url} href={url} target="_blank" rel="noreferrer" style={{ color: '#58a6ff', fontSize: 12 }}>{sourceDomain(url)}</a>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default EvidencePanel;
