import React, { useState } from 'react';
import { InlineFormattedText } from './FormattedText';

const DECISION_LABELS = { PURSUE: 'Pursue', WATCH: 'Watch', DEPRIORITIZE: 'Deprioritize' };

const STATUS = {
  met: { glyph: '✓', label: 'Met' },
  not_met: { glyph: '✗', label: 'Not met' },
  unknown: { glyph: '?', label: 'No evidence' },
};

export function DecisionChip({ decision, large = false }) {
  const key = (decision || 'WATCH').toUpperCase();
  return <span className={`chip chip-${key.toLowerCase()}${large ? ' chip-lg' : ''}`}>{DECISION_LABELS[key] || key}</span>;
}

// "3/5" from the verdict's criteria statuses, or null when the verdict predates the scorecard.
export function fitScore(verdict) {
  const criteria = verdict?.criteria || [];
  if (!criteria.length) return null;
  return { met: criteria.filter((item) => item.status === 'met').length, total: criteria.length };
}

function citedCount(verdict) {
  const items = [...(verdict?.criteria || []), ...(verdict?.signals || [])];
  return new Set(items.flatMap((item) => item?.source_ids || [])).size;
}

// Splits sorted sources into runs of consecutive ids, e.g. 1,2,3,5 -> [[1,2,3],[5]].
function consecutiveRuns(sources) {
  return sources.reduce((runs, source) => {
    const last = runs[runs.length - 1];
    if (last && source.id === last[last.length - 1].id + 1) last.push(source);
    else runs.push([source]);
    return runs;
  }, []);
}

function CitationLink({ source, hot }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      title={source.url}
      className={`cite${hot.id === source.id ? ' is-hot' : ''}`}
      onMouseEnter={() => hot.set(source.id)}
      onMouseLeave={() => hot.set(null)}
      onFocus={() => hot.set(source.id)}
      onBlur={() => hot.set(null)}
    >
      {source.id}
    </a>
  );
}

// A run of 3+ consecutive sources shows as one 5–11 button that expands into the individual links.
function CitationRun({ run, hot }) {
  const [open, setOpen] = useState(false);
  if (run.length < 3 || open) return run.map((source) => <CitationLink key={source.id} source={source} hot={hot} />);
  const first = run[0].id;
  const last = run[run.length - 1].id;
  return (
    <button type="button" className="citation-range" onClick={() => setOpen(true)}
      title={run.map((source) => source.url).join('\n')} aria-label={`Show sources ${first} to ${last}`}>
      {first}–{last}
    </button>
  );
}

// Footnote links to the numbered sources behind a claim. Ids without a known source render nothing.
function Citations({ ids, sources, hot }) {
  const links = [...new Set(ids || [])]
    .map((id) => sources?.find((source) => source.id === id))
    .filter(Boolean)
    .sort((x, y) => x.id - y.id);
  if (!links.length) return null;
  return (
    <sup className="citations" aria-label="Sources">
      {consecutiveRuns(links).map((run) => <CitationRun key={run[0].id} run={run} hot={hot} />)}
    </sup>
  );
}

function VerdictCard({ verdict, company, sources, hotId = null, onHover = () => {} }) {
  const hot = { id: hotId, set: onHover };
  const confidence = verdict?.confidence || 'unknown';
  const fit = fitScore(verdict);

  return (
    <article aria-labelledby="verdict-company">
      <header className="verdict-head">
        <h1 id="verdict-company">{company}</h1>
        <DecisionChip decision={verdict?.decision} large />
      </header>

      <dl className="metrics">
        <div className="metric">
          <dt>confidence</dt>
          <dd>
            <span className="meter" data-level={confidence} aria-hidden="true"><i /><i /><i /></span>
            <span className="capitalize">{confidence}</span>
          </dd>
        </div>
        {fit && (
          <div className="metric">
            <dt>fit</dt>
            <dd><span className="mono">{fit.met}/{fit.total}</span> criteria met</dd>
          </div>
        )}
        {sources?.length > 0 && (
          <div className="metric">
            <dt>sources</dt>
            <dd><span className="mono">{citedCount(verdict)}/{sources.length}</span> cited</dd>
          </div>
        )}
      </dl>
      {verdict?.confidence_note && (
        <p className="confidence-note"><i className="ti ti-alert-triangle" aria-hidden="true" />{verdict.confidence_note}</p>
      )}

      {verdict?.reasoning && <p className="reasoning"><InlineFormattedText text={verdict.reasoning} /></p>}

      {verdict?.next_step && (
        <div className="next-step"><strong>next step</strong>{verdict.next_step}</div>
      )}

      {verdict?.criteria?.length > 0 && (
        <section className="block" aria-labelledby="scorecard-title">
          <div className="block-head">
            <h2 id="scorecard-title">Criteria scorecard</h2>
            {fit && <span className="mono">{fit.met}/{fit.total} met</span>}
          </div>
          <ul className="scorecard">
            {verdict.criteria.map((item, idx) => {
              const status = STATUS[item.status] || STATUS.unknown;
              return (
                <li key={idx} className="score-row">
                  <span className="score-glyph" data-status={item.status in STATUS ? item.status : 'unknown'} title={status.label}>
                    <span aria-hidden="true">{status.glyph}</span><span className="sr-only">{status.label}</span>
                  </span>
                  <span className="score-name">{item.criterion}</span>
                  <span className="score-evidence">{item.evidence}<Citations ids={item.source_ids} sources={sources} hot={hot} /></span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {verdict?.signals?.length > 0 && (
        <section className="block" aria-labelledby="signals-title">
          <div className="block-head"><h2 id="signals-title">Key signals</h2></div>
          <ul className="signals">
            {verdict.signals.map((signal, idx) => (
              <li key={idx}>
                <InlineFormattedText text={signal.text ?? signal} />
                <Citations ids={signal.source_ids} sources={sources} hot={hot} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}

export default VerdictCard;
