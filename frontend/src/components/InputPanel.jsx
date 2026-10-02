import React, { useLayoutEffect, useRef, useState } from 'react';
import Stages from './Stages';
import { DecisionChip, fitScore } from './VerdictCard';

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

function VerdictRow({ company, pitch, verdict, meta, onClick }) {
  const fit = fitScore(verdict);
  return (
    <li>
      <button type="button" className="row" onClick={onClick}>
        <DecisionChip decision={verdict?.decision} />
        <span className="row-company">{company}</span>
        <span className="row-pitch">{pitch}</span>
        <span className="row-meta">
          {fit && <span>fit {fit.met}/{fit.total}</span>}
          <span>{meta}</span>
          <i className="ti ti-arrow-right row-go" aria-hidden="true" />
        </span>
      </button>
    </li>
  );
}

function InputPanel({ onAnalyze, companyName, setCompanyName, productDescription, setProductDescription, companyWebsite, setCompanyWebsite, history, onSelectHistory, examples, onSelectExample }) {
  const [validationError, setValidationError] = useState('');
  const productRef = useRef(null);

  // The product field grows with its text, including a description restored from storage.
  useLayoutEffect(() => {
    const field = productRef.current;
    if (!field) return;
    field.style.height = 'auto';
    field.style.height = `${field.scrollHeight}px`;
  }, [productDescription]);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!companyName.trim() || !productDescription.trim()) {
      setValidationError('Add what you sell and an account to check.');
      return;
    }
    setValidationError('');
    onAnalyze({ company_name: companyName.trim(), product_description: productDescription.trim(), company_website: companyWebsite.trim() || undefined });
  };

  // Cmd/Ctrl+Enter submits from any field, including the multi-line product description.
  const onKeyDown = (event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) handleSubmit(event);
  };

  return (
    <main className="landing">
      <section className="hero" aria-labelledby="hero-title">
        <h1 id="hero-title">Know if an account fits, <span>with every claim sourced.</span></h1>
        <p className="hero-sub">Describe what you sell and name an account. It&apos;s researched, scored against your buying criteria, and comes back as pursue, watch, or move on.</p>

        <form className="command" onSubmit={handleSubmit} onKeyDown={onKeyDown} noValidate aria-label="Check an account">
          <div className="command-field">
            <label htmlFor="product">what you sell</label>
            <textarea id="product" ref={productRef} rows={1} value={productDescription}
              onChange={(event) => setProductDescription(event.target.value)}
              placeholder="Spend management for fast-growing tech companies" />
          </div>
          <div className="command-row">
            <div className="command-field">
              <label htmlFor="company">account</label>
              <input id="company" type="text" value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="Linear" />
            </div>
            <div className="command-field">
              <label htmlFor="website">website <span>(optional)</span></label>
              <input id="website" type="text" inputMode="url" maxLength={200} value={companyWebsite} onChange={(event) => setCompanyWebsite(event.target.value)} placeholder="company.com" />
            </div>
          </div>
          {validationError && <p role="alert" className="form-error">{validationError}</p>}
          <div className="command-foot">
            <span className="command-hint">~25s · 4 sources · every claim cited</span>
            <button className="btn btn-primary" type="submit">
              Check fit <kbd>{IS_MAC ? '⌘' : 'Ctrl'}↵</kbd>
            </button>
          </div>
        </form>
      </section>

      {history?.length > 0 && (
        <section className="section" aria-labelledby="history-title">
          <div className="section-head"><h2 id="history-title">Your recent checks</h2><p>Saved in this browser only.</p></div>
          <ul className="rows">
            {history.slice(0, 5).map((item) => (
              <VerdictRow key={`${item.company_name}-${item.analyzed_at}`} company={item.company_name}
                pitch={item.result?.icp_profile?.raw_description} verdict={item.result?.verdict}
                meta={new Date(item.analyzed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                onClick={() => onSelectHistory(item)} />
            ))}
          </ul>
        </section>
      )}

      <section className="section" id="example" aria-labelledby="example-title">
        <div className="section-head"><h2 id="example-title">Example verdicts</h2><p>Real runs, saved. Open one to see the full dossier.</p></div>
        <ul className="rows">
          {examples.map((example) => (
            <VerdictRow key={example.id} company={example.company_name} pitch={`Selling ${example.product_description?.replace(/\.$/, '').toLowerCase()}`}
              verdict={example.verdict} meta={example.analyzed_at} onClick={() => onSelectExample(example)} />
          ))}
        </ul>
      </section>

      <section className="section" id="how-it-works" aria-labelledby="how-title">
        <div className="section-head"><h2 id="how-title">Method</h2><p>The same three stages you watch while a check runs.</p></div>
        <Stages />
        <p className="method-note">8 model calls per account · edited criteria rerun only the verdict (~7s) · replaces an estimated 20–30 min of manual research</p>
      </section>
    </main>
  );
}

export default InputPanel;
