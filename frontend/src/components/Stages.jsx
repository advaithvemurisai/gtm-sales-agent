import React from 'react';

// The pipeline's real stages, in the order /analyze/stream reports them.
export const STAGES = [
  { id: 'icp', title: 'Criteria', detail: 'What you sell becomes editable buying criteria: size, funding, tech, hiring, budget.' },
  { id: 'research', title: 'Research', detail: 'Fundamentals, news, technology and hiring are searched in parallel on the public web.' },
  { id: 'verdict', title: 'Verdict', detail: 'Each criterion is scored and cited; confidence is capped when evidence is missing.' },
];

function stageState(index, activeIndex, skipped) {
  if (skipped.includes(STAGES[index].id)) return 'skipped';
  if (activeIndex < 0) return 'pending';
  if (index < activeIndex) return 'done';
  return index === activeIndex ? 'active' : 'pending';
}

// `active` unset renders the static method strip; set, it renders the live tracker.
function Stages({ active, skipped = [], vertical = false }) {
  const activeIndex = STAGES.findIndex((stage) => stage.id === active);

  return (
    <ol className={`stages${vertical ? ' stages-vertical' : ''}`}>
      {STAGES.map((stage, index) => {
        const state = active ? stageState(index, activeIndex, skipped) : undefined;
        return (
          <li key={stage.id} className="stage" data-state={state} aria-current={state === 'active' ? 'step' : undefined}>
            {vertical
              ? <span className="stage-dot" aria-hidden="true">{state === 'done' || state === 'skipped' ? <i className="ti ti-check" /> : null}</span>
              : <span className="stage-index">0{index + 1}</span>}
            <h3>
              {stage.title}
              {state === 'skipped' && <span className="muted"> · reused</span>}
              {state && <span className="sr-only"> ({state})</span>}
            </h3>
            <p>{stage.detail}</p>
          </li>
        );
      })}
    </ol>
  );
}

export default Stages;
