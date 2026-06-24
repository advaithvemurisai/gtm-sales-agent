import React, { useState } from 'react';

function InputPanel({ onAnalyze }) {
  const [companyName, setCompanyName] = useState('');
  const [productDescription, setProductDescription] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!companyName.trim() || !productDescription.trim()) {
      alert('Please fill in all required fields');
      return;
    }
    onAnalyze({ company_name: companyName, product_description: productDescription });
  };

  return (
    <div style={{ fontFamily: 'var(--font-sans)', background: 'var(--color-background-primary)', minHeight: '100vh' }}>

      {/* Header */}
      <div style={{ background: 'var(--color-background-secondary)', borderBottom: '0.5px solid var(--color-border-tertiary)', padding: '1.5rem 2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, background: 'var(--color-background-success)', borderRadius: 'var(--border-radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <i className="ti ti-target" style={{ fontSize: 16, color: 'var(--color-text-success)' }} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-text-primary)', letterSpacing: '-0.01em' }}>GTM Sales Intelligence</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 1 }}>Powered by Anthropic</div>
            </div>
          </div>
          <div>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-text-success)', display: 'inline-block', marginRight: 6 }} />
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>4 sources active</span>
          </div>
        </div>

        {/* Signal pills */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { icon: 'ti-building-bank', label: 'Funding data' },
            { icon: 'ti-stack-2', label: 'Tech stack' },
            { icon: 'ti-users', label: 'Hiring signals' },
            { icon: 'ti-world-search', label: 'Live web search' },
          ].map(({ icon, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '6px 12px', borderRadius: 99, border: '0.5px solid var(--color-border-success)', background: 'var(--color-background-success)', fontSize: 12, color: 'var(--color-text-success)' }}>
              <i className={`ti ${icon}`} style={{ fontSize: 14 }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Main form */}
      <div style={{ padding: '2.5rem 2rem', maxWidth: 600, margin: '0 auto' }}>
        <p style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-text-secondary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '0.5rem' }}>Company evaluation</p>
        <h1 style={{ fontSize: 22, fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '0.4rem', letterSpacing: '-0.02em' }}>Who are you targeting?</h1>
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: '2rem', lineHeight: 1.6 }}>
          Enter a company and what you sell. The agent checks funding stage, tech stack, hiring patterns, and recent news to return a verdict.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label htmlFor="company" style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: 6, display: 'block' }}>
              Company name
            </label>
            <input
              id="company"
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="e.g. Notion, Rippling, Brex"
              style={{ width: '100%', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '9px 12px', fontSize: 14, background: 'var(--color-background-primary)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-sans)', outline: 'none' }}
              onFocus={e => { e.target.style.borderColor = 'var(--color-border-success)'; e.target.style.boxShadow = '0 0 0 2px var(--color-background-success)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--color-border-secondary)'; e.target.style.boxShadow = 'none'; }}
            />
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label htmlFor="product" style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: 6, display: 'block' }}>
              What you sell <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12, marginLeft: 4 }}>in one line</span>
            </label>
            <textarea
              id="product"
              rows={2}
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="e.g. Data analytics platform for B2B SaaS companies"
              style={{ width: '100%', border: '0.5px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '9px 12px', fontSize: 14, background: 'var(--color-background-primary)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-sans)', outline: 'none', resize: 'none', lineHeight: 1.5 }}
              onFocus={e => { e.target.style.borderColor = 'var(--color-border-success)'; e.target.style.boxShadow = '0 0 0 2px var(--color-background-success)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--color-border-secondary)'; e.target.style.boxShadow = 'none'; }}
            />
          </div>

          <button
            type="submit"
            style={{ width: '100%', padding: 11, borderRadius: 'var(--border-radius-md)', border: 'none', background: 'var(--color-text-success)', color: 'white', fontSize: 14, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: '1.5rem' }}
            onMouseEnter={e => e.target.style.opacity = '0.88'}
            onMouseLeave={e => e.target.style.opacity = '1'}
          >
            <i className="ti ti-player-play" style={{ fontSize: 14 }} />
            Analyze company
          </button>
        </form>

        <div style={{ height: '0.5px', background: 'var(--color-border-tertiary)', margin: '2rem 0' }} />

        <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', textAlign: 'center', lineHeight: 1.6 }}>
          Returns <strong style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>Pursue</strong>, <strong style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>Watch</strong>, or <strong style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>Deprioritize</strong> with evidence from Crunchbase, BuiltWith, careers pages, and web search.
        </p>
      </div>
    </div>
  );
}

export default InputPanel;
