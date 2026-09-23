import React, { useEffect, useRef, useState } from 'react';
import InputPanel from './components/InputPanel';
import VerdictCard from './components/VerdictCard';
import EvidencePanel from './components/EvidencePanel';
import IcpProfile, { LIST_FIELDS } from './components/IcpProfile';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
// Versioned so results saved under an older response shape are never read back.
const PRODUCT_KEY = 'gtm-agent:v2:product-description';
const COMPANY_KEY = 'gtm-agent:v2:company-name';
const WEBSITE_KEY = 'gtm-agent:v2:company-website';
const HISTORY_KEY = 'gtm-agent:v2:history';
const HISTORY_LIMIT = 8;
const ICP_ITEM_MAX_LENGTH = 80;
const ICP_LIST_LIMITS = { funding_stage: 8, tech_signals: 10, hiring_signals: 10 };

// Storage can be blocked (privacy settings) or hold stale data; never let it break the page.
const storage = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Persistence is a convenience only.
    }
  },
};

function loadHistory() {
  const saved = storage.get(HISTORY_KEY, []);
  return Array.isArray(saved) ? saved.filter((item) => item?.result?.verdict && item?.result?.icp_profile) : [];
}

function loadingMessage(seconds) {
  if (seconds < 5) return 'Reading what you sell and building the ideal customer profile...';
  if (seconds < 35) return 'Searching the web for company, technology, and hiring signals...';
  if (seconds < 60) return 'Summarizing the evidence against your ideal customer profile...';
  return 'Writing the verdict. Slower searches can take up to two minutes...';
}

const NETWORK_ERROR = "Couldn't reach the server. It may be starting up; try again in a minute.";

function requestError(message, code) {
  return Object.assign(new Error(message), { code });
}

function errorMessage(payload) {
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail)) return 'Some of the details were not accepted. Check the criteria and try again.';
  return 'Analysis failed. Please try again.';
}

function draftFromProfile(profile) {
  return Object.fromEntries(
    ['target_company_size', 'budget_indicator', ...LIST_FIELDS].map((key) => {
      const value = profile?.[key];
      return [key, Array.isArray(value) ? value.join(', ') : value || ''];
    }),
  );
}

function profileFromDraft(draft) {
  const profile = {
    target_company_size: draft.target_company_size.trim() || null,
    budget_indicator: draft.budget_indicator.trim() || null,
  };
  for (const key of LIST_FIELDS) {
    profile[key] = draft[key].split(',').map((item) => item.trim()).filter(Boolean);
  }
  return profile;
}

function validateProfile(profile) {
  for (const [key, limit] of Object.entries(ICP_LIST_LIMITS)) {
    if (profile[key].length > limit) return `Keep ${key.replace('_', ' ')} to ${limit} items or fewer.`;
  }
  const values = [profile.target_company_size, profile.budget_indicator, ...LIST_FIELDS.flatMap((key) => profile[key])];
  if (values.some((value) => value && value.length > ICP_ITEM_MAX_LENGTH)) {
    return `Keep each criterion under ${ICP_ITEM_MAX_LENGTH} characters.`;
  }
  return null;
}

function App() {
  const healthStarted = useRef(false);
  const [phase, setPhase] = useState('input');
  const [companyData, setCompanyData] = useState(null);
  const [companyName, setCompanyName] = useState(() => storage.get(COMPANY_KEY, ''));
  const [companyWebsite, setCompanyWebsite] = useState(() => storage.get(WEBSITE_KEY, ''));
  const [productDescription, setProductDescription] = useState(() => storage.get(PRODUCT_KEY, ''));
  const [history, setHistory] = useState(loadHistory);
  const [icpDraft, setIcpDraft] = useState(null);
  const [icpError, setIcpError] = useState(null);
  const [copyStatus, setCopyStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRequest, setLastRequest] = useState(null);
  const exampleModules = import.meta.glob('./examples/*.json', { eager: true, import: 'default' });
  const DECISION_ORDER = { PURSUE: 0, WATCH: 1, DEPRIORITIZE: 2 };
  const examples = Object.values(exampleModules)
    .sort((a, b) => (DECISION_ORDER[a.verdict?.decision] ?? 3) - (DECISION_ORDER[b.verdict?.decision] ?? 3))
    .map((example, index) => ({
    ...example,
    id: example.company_name || index,
    label: example.verdict?.decision === 'PURSUE' ? 'Good fit' : example.verdict?.decision === 'WATCH' ? 'Worth watching' : 'Not a fit',
    analyzed_at: new Date(example.analyzed_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
  }));
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => { storage.set(PRODUCT_KEY, productDescription); }, [productDescription]);
  useEffect(() => { storage.set(COMPANY_KEY, companyName); }, [companyName]);
  useEffect(() => { storage.set(WEBSITE_KEY, companyWebsite); }, [companyWebsite]);
  useEffect(() => { storage.set(HISTORY_KEY, history); }, [history]);

  useEffect(() => {
    if (healthStarted.current) return;
    healthStarted.current = true;
    fetch(`${API_BASE_URL}/health`).catch(() => {});
  }, []);

  useEffect(() => {
    if (!loading) return undefined;
    const startedAt = Date.now();
    setElapsedSeconds(0);
    const timer = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (!copyStatus) return undefined;
    const timer = setTimeout(() => setCopyStatus(''), 2500);
    return () => clearTimeout(timer);
  }, [copyStatus]);

  const showResult = (result) => {
    setCompanyData(result);
    setIcpDraft(null);
    setIcpError(null);
    setCopyStatus('');
    setPhase('result');
  };

  const handleAnalyze = async (data, icpProfile = null) => {
    setLoading(true);
    setError(null);
    setCompanyName(data.company_name);
    setProductDescription(data.product_description);
    setCompanyWebsite(data.company_website || '');
    setLastRequest({ ...data, icp_profile: icpProfile });

    try {
      // Only a failed fetch means the server was unreachable; other errors keep their own message.
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...data, icp_profile: icpProfile }),
      }).catch(() => { throw requestError(NETWORK_ERROR, 'network'); });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw requestError(errorMessage(payload), payload?.code || 'server');
      }

      const result = await response.json();
      showResult(result);
      setHistory((current) => [
        { company_name: result.company_name, decision: result.verdict.decision, analyzed_at: new Date().toISOString(), result },
        ...current.filter((item) => item.company_name !== result.company_name),
      ].slice(0, HISTORY_LIMIT));
    } catch (err) {
      setError({ message: err.code ? err.message : 'Something went wrong showing the result. Please try again.', code: err.code || 'client' });
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartOver = () => {
    setPhase('input');
    setCompanyData(null);
    setIcpDraft(null);
    setError(null);
  };

  const handleCopy = async () => {
    const verdict = companyData.verdict;
    const lines = [
      `${companyData.company_name}: ${verdict.decision} (confidence: ${verdict.confidence})`,
      verdict.reasoning,
      ...(verdict.signals || []).map((signal) => `- ${signal}`),
      verdict.next_step && `Next step: ${verdict.next_step}`,
    ].filter(Boolean);
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyStatus('Copied');
    } catch {
      setCopyStatus("Couldn't copy. Select the text manually.");
    }
  };

  const rerunWithIcp = () => {
    const profile = profileFromDraft(icpDraft);
    const problem = validateProfile(profile);
    if (problem) {
      setIcpError(problem);
      return;
    }
    // Rerun with the product this result was analyzed for, which may be a saved example's.
    handleAnalyze({
      company_name: companyData.company_name,
      product_description: companyData.icp_profile?.raw_description || productDescription,
      company_website: companyData.saved_example ? undefined : companyWebsite,
    }, profile);
  };

  return (
    <div className="app-shell">
      <header className="app-header"><strong>GTM Agent</strong><nav><a href="#how-it-works">How it works</a><a href="#example">Example</a></nav></header>
      {error && (
        <div className={`notice ${error.code === 'demo_paused' ? 'notice-paused' : 'notice-error'}`} role="alert">
          <span>{error.code === 'demo_paused' ? 'Live research is paused right now. ' : error.message}</span>
          {error.code === 'demo_paused' && phase === 'input' && <a href="#example">See a real example below.</a>}
          {error.code === 'network' && lastRequest && <button type="button" onClick={() => handleAnalyze(lastRequest, lastRequest.icp_profile)}>Try again</button>}
        </div>
      )}

      {loading && (
        <div role="status" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '70vh', flexDirection: 'column', gap: 16, padding: '0 1rem' }}>
          <div className="animate-spin" style={{ width: 32, height: 32, border: '2px solid var(--color-border-primary)', borderTopColor: 'var(--color-text-success)', borderRadius: '50%' }} />
          <p style={{ color: 'var(--color-text-primary)', fontSize: 15, textAlign: 'center', maxWidth: 420, margin: 0 }}>Researching {companyName}</p>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 13, textAlign: 'center', maxWidth: 380, margin: 0 }}>
            {loadingMessage(elapsedSeconds)}
          </p>
          <p className="muted-text">{elapsedSeconds}s elapsed · usually 30–90 seconds</p>
        </div>
      )}

      {!loading && phase === 'input' && (
        <InputPanel
          onAnalyze={handleAnalyze}
          companyName={companyName}
          setCompanyName={setCompanyName}
          productDescription={productDescription}
          setProductDescription={setProductDescription}
          companyWebsite={companyWebsite}
          setCompanyWebsite={setCompanyWebsite}
          history={history}
          examples={examples}
          onSelectExample={(example) => showResult({ ...example, saved_example: true })}
          onSelectHistory={(item) => {
            setCompanyName(item.company_name);
            setProductDescription(item.result.icp_profile?.raw_description || productDescription);
            showResult(item.result);
          }}
        />
      )}

      {!loading && phase === 'result' && companyData && (
        <div style={{ maxWidth: 760, margin: '0 auto', padding: '2rem 1rem' }}>
          {companyData.saved_example && (
            <p className="saved-banner">
              Saved example · analyzed {companyData.analyzed_at} · selling &ldquo;{companyData.product_description?.replace(/\.$/, '')}&rdquo;{' '}·{' '}
              <button type="button" onClick={handleStartOver}>Research your own account</button>
            </p>
          )}
          <VerdictCard verdict={companyData.verdict} company={companyData.company_name} />
          <div className="result-actions">
            <button className="secondary-button" type="button" onClick={handleCopy}>Copy summary</button>
            <span className="muted-text" role="status" aria-live="polite">{copyStatus}</span>
          </div>
          <IcpProfile
            profile={companyData.icp_profile}
            draft={icpDraft}
            error={icpError}
            onEdit={() => { setIcpDraft(draftFromProfile(companyData.icp_profile)); setIcpError(null); }}
            onChange={(key, value) => setIcpDraft((current) => ({ ...current, [key]: value }))}
            onCancel={() => { setIcpDraft(null); setIcpError(null); }}
            onRerun={rerunWithIcp}
          />
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
