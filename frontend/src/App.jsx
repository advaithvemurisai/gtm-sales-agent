import React, { useState } from 'react';
import InputPanel from './components/InputPanel';
import VerdictCard from './components/VerdictCard';
import EvidencePanel from './components/EvidencePanel';
import './App.css';

function App() {
  const [phase, setPhase] = useState('input'); // input, chat, result
  const [companyData, setCompanyData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async (data) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error('Failed to analyze company');
      }

      const result = await response.json();
      setCompanyData(result);
      setPhase('result');
    } catch (err) {
      setError(err.message);
      console.error('Error:', err);
    } finally {
      setLoading(false);
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
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 14, textAlign: 'center', maxWidth: 360 }}>Running web searches, extracting signals, checking tech stack...</p>
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
