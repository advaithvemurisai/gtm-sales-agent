import React, { useState } from 'react';

function InputPanel({ onAnalyze, companyName, setCompanyName, productDescription, setProductDescription, companyWebsite, setCompanyWebsite, history, onSelectHistory, examples, onSelectExample }) {
  const [validationError, setValidationError] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!companyName.trim() || !productDescription.trim()) {
      setValidationError('Add an account and a short description of what you sell.');
      return;
    }
    setValidationError('');
    onAnalyze({ company_name: companyName.trim(), product_description: productDescription.trim(), company_website: companyWebsite.trim() || undefined });
  };

  return (
    <main className="landing-page">
      <section className="hero-section" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="hero-kicker">Account research for focused sales teams</p>
          <h1 id="hero-title">Know which accounts are worth your team&apos;s time.</h1>
          <p className="hero-lede">Research a target account in about a minute, covering fit against who you sell to, why now, and who to contact, with every claim sourced.</p>
          <div className="trust-points" aria-label="Product benefits">
            <span><i className="ti ti-check" />Sourced evidence</span>
            <span><i className="ti ti-adjustments" />Your criteria, editable</span>
          </div>
        </div>

        <form className="research-form" onSubmit={handleSubmit} noValidate>
          <div className="form-heading"><p className="eyebrow">Start a review</p><h2>Research an account</h2><p>Tell us what you sell and who you are considering.</p></div>
          <label htmlFor="product">Your product
            <textarea id="product" rows={4} value={productDescription} onChange={(event) => setProductDescription(event.target.value)} placeholder="e.g. Spend management for fast-growing technology companies" />
          </label>
          <label htmlFor="company">Account to research
            <input id="company" type="text" value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="e.g. Notion, Rippling, Brex" />
          </label>
          <label htmlFor="website">Company website <span>(optional)</span>
            <input id="website" type="url" maxLength={200} value={companyWebsite} onChange={(event) => setCompanyWebsite(event.target.value)} placeholder="e.g. notion.so" />
          </label>
          {validationError && <p role="alert" className="form-error">{validationError}</p>}
          <button className="primary-button research-button" type="submit">Research account <i className="ti ti-arrow-right" /></button>
          <p className="form-note">You&apos;ll get a clear verdict, the reasoning behind it, and the evidence to share with your team.</p>
        </form>
      </section>

      <section className="landing-section example-section" id="example" aria-labelledby="example-title">
        <div className="section-intro"><p className="eyebrow">See a real result</p><h2 id="example-title">A useful answer, not another list of accounts.</h2></div>
        {examples.length > 0 ? <div className="example-tabs" role="group" aria-label="Saved examples">{examples.map((example) => <button key={example.id} type="button" onClick={() => onSelectExample(example)}><span className={`example-verdict example-verdict-${example.verdict.decision.toLowerCase()}`}>{example.label}</span><strong>{example.company_name}</strong><span className="example-pitch">Selling: {example.product_description}</span><small>Saved example · analyzed {example.analyzed_at}</small></button>)}</div> : <figure className="example-image"><img src="/result.png" alt="Example account research result" /><figcaption>Example result</figcaption></figure>}
      </section>

      <section className="landing-section how-section" id="how-it-works" aria-labelledby="how-title">
        <div className="section-intro"><p className="eyebrow">How it works</p><h2 id="how-title">From a hunch to a defensible next step.</h2></div>
        <div className="steps-grid">
          <article><span>01</span><h3>Describe what you sell</h3><p>Share your product in plain language. We turn it into clear, editable buying criteria.</p></article>
          <article><span>02</span><h3>We research the company</h3><p>We search the public web for company facts, technology, hiring, and recent news.</p></article>
          <article><span>03</span><h3>Get a verdict you can defend</h3><p>See whether to pursue, watch, or deprioritize the account, with sources and a next step.</p></article>
        </div>
      </section>

      <section className="landing-section audience-section" aria-labelledby="audience-title">
        <div><p className="eyebrow">Who it&apos;s for</p><h2 id="audience-title">More signal for every person doing the work.</h2></div>
        <div className="audience-list"><span>Founders doing their own sales</span><span>SDRs building focused lists</span><span>AEs planning the first call</span><span>RevOps setting a shared standard</span></div>
        <p className="time-saved">Replaces an <strong>estimated 20–30 minutes</strong> of manual research per account.</p>
      </section>

      {history?.length > 0 && <section className="history-panel" aria-labelledby="history-title"><p className="eyebrow">Recent account reviews</p><h2 id="history-title">Pick up where you left off</h2>{history.slice(0, 5).map((item) => <button className="history-row" key={`${item.company_name}-${item.analyzed_at}`} type="button" onClick={() => onSelectHistory(item)}><span>{item.company_name}</span><strong>{item.decision}</strong></button>)}</section>}
    </main>
  );
}

export default InputPanel;
