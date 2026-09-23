import React from 'react';

const FIELDS = [
  ['target_company_size', 'Target company size', 'e.g. 50-500 employees'],
  ['funding_stage', 'Funding stages', 'Comma-separated, e.g. Series A, Series B'],
  ['tech_signals', 'Technology they use', 'Comma-separated, e.g. Salesforce, HubSpot'],
  ['hiring_signals', 'Relevant hiring roles', 'Comma-separated, e.g. VP Finance, RevOps Lead'],
  ['budget_indicator', 'Budget tier', 'e.g. mid-market'],
];

export const LIST_FIELDS = ['funding_stage', 'tech_signals', 'hiring_signals'];

function displayValue(value) {
  if (Array.isArray(value)) return value.join(', ');
  return value || '';
}

function IcpProfile({ profile, draft, error, onEdit, onChange, onCancel, onRerun }) {
  const editing = draft !== null;

  return (
    <section className="icp-panel" aria-labelledby="icp-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">The criteria used</p>
          <h3 id="icp-title">Ideal customer profile</h3>
        </div>
        {!editing && <button className="secondary-button" type="button" onClick={onEdit}>Edit criteria</button>}
      </div>
      <p className="panel-copy">
        {editing
          ? 'Adjust any criterion, then rerun. Separate list items with commas.'
          : 'Inferred from what you sell. The verdict is only as good as these assumptions, so check them.'}
      </p>

      {editing ? (
        <div className="icp-grid">
          {FIELDS.map(([key, label, placeholder]) => (
            <label key={key}>
              <span>{label}</span>
              <input value={draft[key]} onChange={(event) => onChange(key, event.target.value)} placeholder={placeholder} />
            </label>
          ))}
        </div>
      ) : (
        <dl className="icp-grid">
          {FIELDS.map(([key, label]) => (
            <div key={key} className="icp-item">
              <dt>{label}</dt>
              <dd className={displayValue(profile?.[key]) ? '' : 'muted-text'}>{displayValue(profile?.[key]) || 'Not specified'}</dd>
            </div>
          ))}
        </dl>
      )}

      {error && <p role="alert" className="form-error">{error}</p>}
      {editing && (
        <div className="result-actions">
          <button className="primary-button" type="button" onClick={onRerun}>Rerun with these criteria</button>
          <button className="secondary-button" type="button" onClick={onCancel}>Cancel</button>
        </div>
      )}
    </section>
  );
}

export default IcpProfile;
