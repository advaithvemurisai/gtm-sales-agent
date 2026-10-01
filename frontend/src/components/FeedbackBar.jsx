import React, { useState } from 'react';

// Collects a label (and optional reason) for each verdict. Stored in the browser only; these become
// the ground truth for the eval set once exported.
function FeedbackBar({ feedback, onChange }) {
  const [why, setWhy] = useState(feedback?.why || '');
  const vote = feedback?.vote;

  return (
    <div className="feedback">
      <span>Useful?</span>
      {[['up', 'ti-thumb-up', 'Useful'], ['down', 'ti-thumb-down', 'Not useful']].map(([value, icon, label]) => (
        <button key={value} type="button" className="icon-btn" aria-pressed={vote === value} aria-label={label} title={label}
          onClick={() => onChange({ vote: vote === value ? null : value, why })}>
          <i className={`ti ${icon}`} aria-hidden="true" />
        </button>
      ))}
      {vote && (
        <input type="text" value={why} maxLength={200} placeholder="Why? (optional)" aria-label="Why"
          onChange={(event) => setWhy(event.target.value)}
          onBlur={() => onChange({ vote, why })} />
      )}
    </div>
  );
}

export default FeedbackBar;
