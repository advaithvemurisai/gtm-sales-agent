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
    <div style={{ minHeight: '100vh', background: 'var(--color-background-primary)', padding: '2rem 1rem', color: 'var(--color-text-primary)' }}>
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <div style={{ border: '1px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', background: 'var(--color-background-secondary)', padding: '2rem', marginBottom: '2rem' }}>
          <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            Sales targeting assistant
          </p>
          <h1 style={{ fontSize: 30, fontWeight: 700, color: 'var(--color-text-primary)', margin: 0, lineHeight: 1.05, marginBottom: 12 }}>
            Evaluate a target company
          </h1>
          <p style={{ fontSize: 15, color: 'var(--color-text-secondary)', lineHeight: 1.8, margin: 0 }}>
            Enter a company name and product description, then the agent will analyze signals from tech stack, hiring, and recent web activity.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '1rem' }}>
          <label htmlFor="company" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
            Company name
            <input
              id="company"
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="e.g. Notion, Rippling, Brex"
              style={{ width: '100%', marginTop: 8, border: '1px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '12px', fontSize: 15, background: 'var(--color-background-primary)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-sans)', outline: 'none' }}
            />
          </label>

          <label htmlFor="product" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
            What you sell
            <textarea
              id="product"
              rows={3}
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="e.g. Data analytics platform for B2B SaaS companies"
              style={{ width: '100%', marginTop: 8, border: '1px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', padding: '12px', fontSize: 15, background: 'var(--color-background-primary)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-sans)', outline: 'none', resize: 'vertical', lineHeight: 1.6 }}
            />
          </label>

          <button
            type="submit"
            style={{ width: '100%', padding: 14, borderRadius: 'var(--border-radius-md)', border: 'none', background: 'var(--color-text-success)', color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', transition: 'opacity 0.15s ease' }}
          >
            Analyze company
          </button>
        </form>

        <div style={{ marginTop: '1.75rem', border: '1px solid var(--color-border-secondary)', borderRadius: 'var(--border-radius-md)', background: 'rgba(255, 255, 255, 0.03)', padding: '1.35rem' }}>
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', lineHeight: 1.8, margin: 0 }}>
            Returns <strong style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Pursue</strong>, <strong style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Watch</strong>, or <strong style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Deprioritize</strong> with company signals, tech stack, hiring data, and web search.
          </p>
        </div>
      </div>
    </div>
  );
}

export default InputPanel;
