import React, { useEffect, useRef, useState } from 'react';
import InputPanel from './components/InputPanel';
import VerdictCard from './components/VerdictCard';
import EvidencePanel from './components/EvidencePanel';
import FeedbackBar from './components/FeedbackBar';
import SourceLedger from './components/SourceLedger';
import Stages, { STAGES } from './components/Stages';
import IcpProfile, { LIST_FIELDS } from './components/IcpProfile';
import './App.css';

export const BRAND = 'Pursue';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
// Versioned so results saved under an older response shape are never read back.
const PRODUCT_KEY = 'gtm-agent:v2:product-description';
const COMPANY_KEY = 'gtm-agent:v2:company-name';
const WEBSITE_KEY = 'gtm-agent:v2:company-website';
const HISTORY_KEY = 'gtm-agent:v2:history';
const ICP_STORE_KEY = 'gtm-agent:v2:icp-by-product';
const ICP_FIELDS = ['target_company_size', 'funding_stage', 'tech_signals', 'hiring_signals', 'budget_indicator'];
const FEEDBACK_KEY = 'gtm-agent:v2:feedback';
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

// The ICP is a property of the product, not the account. Reusing it keeps verdicts comparable across companies.
function productHash(description) {
  let hash = 5381;
  for (const char of description.trim().toLowerCase()) hash = ((hash * 33) ^ char.charCodeAt(0)) >>> 0;
  return String(hash);
}

function pickIcp(profile) {
  const icp = Object.fromEntries(ICP_FIELDS.map((key) => [key, profile?.[key] ?? (LIST_FIELDS.includes(key) ? [] : null)]));
  return ICP_FIELDS.some((key) => (Array.isArray(icp[key]) ? icp[key].length : icp[key])) ? icp : null;
}

const resultKey = (result) => `${result?.company_name}|${result?.icp_profile?.raw_description || ''}`;
const historyKey = (item) => `${item.company_name}|${item.result?.icp_profile?.raw_description || ''}`;

function loadHistory() {
  const saved = storage.get(HISTORY_KEY, []);
  return Array.isArray(saved) ? saved.filter((item) => item?.result?.verdict && item?.result?.icp_profile) : [];
}


// Reads the /analyze/stream server-sent events: `stage` updates, then one `result` or `error`.
async function readAnalysisStream(response, onStage) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop();
    for (const frame of frames) {
      const event = /^event: (.+)$/m.exec(frame)?.[1];
      const data = /^data: (.+)$/m.exec(frame)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data);
      if (event === 'stage') onStage(payload.stage);
      else if (event === 'result') return payload;
      else if (event === 'error') throw requestError(payload.detail, payload.code);
    }
  }
  throw requestError('The analysis ended before a result arrived. Please try again.', 'server');
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
  const landingScroll = useRef(0);
  const [phase, setPhase] = useState('input');
  const [companyData, setCompanyData] = useState(null);
  const [companyName, setCompanyName] = useState(() => storage.get(COMPANY_KEY, ''));
  const [companyWebsite, setCompanyWebsite] = useState(() => storage.get(WEBSITE_KEY, ''));
  const [productDescription, setProductDescription] = useState(() => storage.get(PRODUCT_KEY, ''));
  const [history, setHistory] = useState(loadHistory);
  const [feedback, setFeedback] = useState(() => storage.get(FEEDBACK_KEY, {}));
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
  const [stage, setStage] = useState('research');
  const [seenStages, setSeenStages] = useState([]);
  const [hotSourceId, setHotSourceId] = useState(null);
  const [pendingSection, setPendingSection] = useState(null);

  useEffect(() => { storage.set(PRODUCT_KEY, productDescription); }, [productDescription]);
  useEffect(() => { storage.set(COMPANY_KEY, companyName); }, [companyName]);
  useEffect(() => { storage.set(WEBSITE_KEY, companyWebsite); }, [companyWebsite]);
  useEffect(() => { storage.set(HISTORY_KEY, history); }, [history]);
  useEffect(() => { storage.set(FEEDBACK_KEY, feedback); }, [feedback]);

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

  // Each result is its own browser history entry, so Back returns to the landing page
  // and Forward reopens the result.
  useEffect(() => {
    // The app switches views itself, so it also owns scroll position (see the effect below).
    if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual';
    const onPopState = (event) => {
      setIcpDraft(null);
      setError(null);
      setPhase(event.state?.view === 'result' ? 'result' : 'input');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  // Results open at the top; the landing page returns to where the user left it,
  // or to the section a header link asked for.
  useEffect(() => {
    if (phase === 'result') {
      window.scrollTo({ top: 0, behavior: 'instant' });
      return;
    }
    if (phase !== 'input') return;
    if (pendingSection === 'top') window.scrollTo({ top: 0, behavior: 'instant' });
    else if (pendingSection) document.getElementById(pendingSection)?.scrollIntoView({ behavior: 'instant' });
    else window.scrollTo({ top: landingScroll.current, behavior: 'instant' });
    landingScroll.current = window.scrollY;
    setPendingSection(null);
  }, [phase, pendingSection, companyData]);

  useEffect(() => {
    if (!copyStatus) return undefined;
    const timer = setTimeout(() => setCopyStatus(''), 2500);
    return () => clearTimeout(timer);
  }, [copyStatus]);

  const showResult = (result) => {
    if (phase === 'input') landingScroll.current = window.scrollY;
    setCompanyData(result);
    setIcpDraft(null);
    setIcpError(null);
    setCopyStatus('');
    setPhase('result');
    const entry = { view: 'result' };
    if (window.history.state?.view === 'result') window.history.replaceState(entry, '', window.location.pathname);
    else window.history.pushState(entry, '', window.location.pathname);
  };

  const handleAnalyze = async (data, icpProfile = null) => {
    setLoading(true);
    const firstStage = icpProfile ? 'research' : 'icp';
    setStage(firstStage);
    setSeenStages([firstStage]);
    setError(null);
    setCompanyName(data.company_name);
    setProductDescription(data.product_description);
    setCompanyWebsite(data.company_website || '');
    const savedIcp = icpProfile || storage.get(ICP_STORE_KEY, {})[productHash(data.product_description)] || null;
    icpProfile = savedIcp;
    setLastRequest({ ...data, icp_profile: icpProfile });

    try {
      // Only a failed fetch means the server was unreachable; other errors keep their own message.
      const post = (path) => fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...data, icp_profile: icpProfile }),
      }).catch(() => { throw requestError(NETWORK_ERROR, 'network'); });

      let response = await post('/analyze/stream');
      // A backend deployed before streaming existed has only /analyze; fall back without stage updates.
      const streaming = response.status !== 404;
      if (!streaming) response = await post('/analyze');

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw requestError(errorMessage(payload), payload?.code || 'server');
      }

      const result = streaming
        ? await readAnalysisStream(response, (next) => {
          setStage(next);
          setSeenStages((seen) => [...seen, next]);
        })
        : await response.json();
      showResult(result);
      const learned = pickIcp(result.icp_profile);
      if (learned) storage.set(ICP_STORE_KEY, { ...storage.get(ICP_STORE_KEY, {}), [productHash(data.product_description)]: learned });
      const entry = { company_name: result.company_name, decision: result.verdict.decision, analyzed_at: new Date().toISOString(), result };
      setHistory((current) => [
        entry,
        ...current.filter((item) => historyKey(item) !== historyKey(entry)),
      ].slice(0, HISTORY_LIMIT));
    } catch (err) {
      setError({ message: err.code ? err.message : 'Something went wrong showing the result. Please try again.', code: err.code || 'client' });
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const goToLanding = (section = 'top') => {
    setPendingSection(section);
    if (phase === 'result' && window.history.state?.view === 'result') {
      window.history.back();
      return;
    }
    setPhase('input');
    setIcpDraft(null);
    setError(null);
  };

  const handleStartOver = () => goToLanding('top');

  const navigate = (section) => (event) => {
    if (phase === 'input' && section !== 'top') return;
    event.preventDefault();
    goToLanding(section);
  };

  const handleCopy = async () => {
    const verdict = companyData.verdict;
    const lines = [
      `${companyData.company_name}: ${verdict.decision} (confidence: ${verdict.confidence})`,
      verdict.reasoning,
      ...(verdict.signals || []).map((signal) => `- ${signal.text ?? signal}`),
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
      <header className="app-header">
        <a className="brand" href="/" onClick={navigate('top')}><svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" /><path d="M10.5 21.5L21 11M13 10.5h8.5V19" /></svg>{BRAND}</a>
        <nav><a href="#example" onClick={navigate('example')}>Examples</a><a href="#how-it-works" onClick={navigate('how-it-works')}>Method</a></nav>
      </header>
      {error && (
        <div className={`notice ${error.code === 'demo_paused' ? 'notice-paused' : 'notice-error'}`} role="alert">
          <span>{error.code === 'demo_paused' ? 'Live research is paused right now. ' : error.message}</span>
          {error.code === 'demo_paused' && phase === 'input' && <a href="#example">See a real example below.</a>}
          {error.code === 'network' && lastRequest && <button type="button" onClick={() => handleAnalyze(lastRequest, lastRequest.icp_profile)}>Try again</button>}
        </div>
      )}

      {loading && (
        <div role="status" aria-live="polite" className="loading">
          <h1 className="loading-title">Checking {companyName}<span>…</span></h1>
          <Stages vertical active={stage} skipped={STAGES.slice(0, STAGES.findIndex(({ id }) => id === stage)).map(({ id }) => id).filter((id) => !seenStages.includes(id))} />
          <p className="elapsed">{String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')}:{String(elapsedSeconds % 60).padStart(2, '0')} elapsed · usually 20–60s</p>
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
        <div className="dossier">
          <main className="dossier-main">
            {companyData.saved_example && (
              <p className="saved-banner">
                <span className="mono">saved example · {companyData.analyzed_at}</span>
                <span>Selling &ldquo;{companyData.product_description?.replace(/\.$/, '')}&rdquo;</span>
                <button type="button" className="link-button" onClick={handleStartOver}>Check your own account</button>
              </p>
            )}
            <VerdictCard verdict={companyData.verdict} company={companyData.company_name} sources={companyData.evidence?.sources}
              hotId={hotSourceId} onHover={setHotSourceId} />
            <div className="toolbar">
              <button className="btn" type="button" onClick={handleCopy}><i className="ti ti-copy" aria-hidden="true" />Copy summary</button>
              <span className="status-text" role="status" aria-live="polite">{copyStatus}</span>
              <span className="toolbar-spacer" />
              {!companyData.saved_example && (
                <FeedbackBar key={resultKey(companyData)} feedback={feedback[resultKey(companyData)]}
                  onChange={(value) => setFeedback((current) => ({ ...current, [resultKey(companyData)]: { ...value, decision: companyData.verdict.decision, at: new Date().toISOString() } }))} />
              )}
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
            <button type="button" className="btn new-account" onClick={handleStartOver}><i className="ti ti-arrow-left" aria-hidden="true" />Check another account</button>
          </main>
          <aside className="dossier-aside">
            <SourceLedger sources={companyData.evidence?.sources} hotId={hotSourceId} onHover={setHotSourceId} />
          </aside>
        </div>
      )}
    </div>
  );
}

export default App;
