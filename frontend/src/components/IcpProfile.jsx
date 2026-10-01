import React from 'react';

const FIELDS = [
  ['target_company_size', 'Company size', 'e.g. 50-500 employees'],
  ['funding_stage', 'Funding stage', 'Comma-separated, e.g. Series A, Series B'],
  ['tech_signals', 'Tech they use', 'Comma-separated, e.g. Salesforce, HubSpot'],
  ['hiring_signals', 'Hiring for', 'Comma-separated, e.g. VP Finance, RevOps Lead'],
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
    <section className="block icp-panel" aria-labelledby="icp-title">
      <div className="block-head">
        <h2 id="icp-title">Criteria used</h2>
        {!editing && <button className="btn btn-ghost" type="button" onClick={onEdit}><i className="ti ti-pencil" aria-hidden="true" />Edit</button>}
      </div>

      {editing ? (
        <>
          <p className="icp-note">Adjust any criterion, then rerun. Research is reused, so only the verdict is regenerated.</p>
          <div className="icp-grid">
            {FIELDS.map(([key, label, placeholder]) => (
              <label key={key}>
                {label}
                <input value={draft[key]} onChange={(event) => onChange(key, event.target.value)} placeholder={placeholder} />
              </label>
            ))}
          </div>
          {error && <p role="alert" className="form-error">{error}</p>}
          <div className="icp-actions">
            <button className="btn btn-primary" type="button" onClick={onRerun}>Rerun verdict</button>
            <button className="btn" type="button" onClick={onCancel}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          <dl className="icp-list">
            {FIELDS.map(([key, label]) => (
              <div key={key} className="icp-row">
                <dt>{label}</dt>
                <dd className={displayValue(profile?.[key]) ? undefined : 'muted'}>{displayValue(profile?.[key]) || 'Not specified'}</dd>
              </div>
            ))}
          </dl>
          <p className="icp-note">Inferred from what you sell. The verdict is only as good as these assumptions.</p>
        </>
      )}
    </section>
  );
}

export default IcpProfile;
