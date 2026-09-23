import React, { useState } from 'react';
import InputPanel from './components/InputPanel';
import VerdictCard from './components/VerdictCard';
import EvidencePanel from './components/EvidencePanel';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [phase, setPhase] = useState('input');
  const [companyData, setCompanyData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadingStep, setLoadingStep] = useState(0);

  const handleAnalyze = async (data) => {
    setLoading(true);
    setError(null);
    const progress = [
      setTimeout(() => setLoadingStep(1), 2500),
      setTimeout(() => setLoadingStep(2), 8000),
      setTimeout(() => setLoadingStep(3), 16000),
    ];

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || 'Analysis failed. Please try again.');
      }

      const result = await response.json();
      setCompanyData(result);
      setPhase('result');
    } catch (err) {
      setError(err.message);
      console.error('Error:', err);
    } finally {
      progress.forEach(clearTimeout);
      setLoading(false);
      setLoadingStep(0);
    }
  };

  const handleStartOver = () => {
    setPhase('input');
    setCompanyData(null);
    setError(null);
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-background-primary)', color: 'var(--color-text-primary)' }}>
      {error && (
        <div style={{ padding: '1rem 1.5rem', background: 'rgba(248,81,73,0.1)', borderBottom: '1px solid rgba(248,81,73,0.35)', color: '#f85149', fontSize: 14 }}>
          Error: {error}
        </div>
      )}

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', flexDirection: 'column', gap: 16, padding: '0 1rem' }}>
          <div className="animate-spin" style={{ width: 32, height: 32, border: '2px solid var(--color-border-primary)', borderTopColor: 'var(--color-text-success)', borderRadius: '50%' }} />
          <p style={{ color: 'var(--color-text-primary)', fontSize: 15, textAlign: 'center', maxWidth: 360, margin: 0 }}>Analyzing signals</p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 13, textAlign: 'center', maxWidth: 360, margin: 0 }}>
            {['Finding company context...', 'Checking technology and hiring signals...', 'Comparing evidence with your ICP...', 'Writing the sales verdict...'][loadingStep]}
          </p>
        </div>
      )}

      {!loading && phase === 'input' && (
        <InputPanel onAnalyze={handleAnalyze} />
      )}

      {!loading && phase === 'result' && companyData && (
        <div style={{ maxWidth: 760, margin: '0 auto', padding: '2rem 1rem' }}>
          <VerdictCard verdict={companyData.verdict} company={companyData.company_name} />
          <EvidencePanel evidence={companyData.evidence} />
          <button
            onClick={handleStartOver}
            style={{ width: '100%', marginTop: '1.5rem', padding: '13px', borderRadius: 'var(--border-radius-md)', border: '1px solid var(--color-border-secondary)', background: 'var(--color-background-secondary)', color: 'var(--color-text-secondary)', fontSize: 14, cursor: 'pointer' }}
          >
            Analyze another company
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
