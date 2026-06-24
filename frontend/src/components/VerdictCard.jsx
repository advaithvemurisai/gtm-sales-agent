import React from 'react';

function VerdictCard({ verdict, company }) {
  const getDecisionColor = (decision) => {
    switch (decision.toUpperCase()) {
      case 'PURSUE':
        return 'bg-green-500/20 border-green-500/50 text-green-300';
      case 'DEPRIORITIZE':
        return 'bg-red-500/20 border-red-500/50 text-red-300';
      case 'WATCH':
        return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300';
      default:
        return 'bg-slate-700 border-slate-600 text-slate-300';
    }
  };

  const getDecisionIcon = (decision) => {
    switch (decision.toUpperCase()) {
      case 'PURSUE':
        return '✓';
      case 'DEPRIORITIZE':
        return '✕';
      case 'WATCH':
        return '●';
      default:
        return '○';
    }
  };

  return (
    <div className={`rounded-lg p-8 border ${getDecisionColor(verdict.decision)}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">{company}</h2>
          <p className="text-sm text-slate-400">Sales Targeting Verdict</p>
        </div>
        <div className="text-5xl font-bold opacity-20">
          {getDecisionIcon(verdict.decision)}
        </div>
      </div>

      <div className="mb-6">
        <div className="inline-block px-4 py-2 rounded-lg bg-slate-700/50 text-white font-bold text-lg">
          {verdict.decision.toUpperCase()}
        </div>
      </div>

      <p className="text-slate-200 mb-6 leading-relaxed">
        {verdict.reasoning}
      </p>

      {verdict.signals && verdict.signals.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-300 mb-3">Key Signals</h3>
          <ul className="space-y-2">
            {verdict.signals.map((signal, idx) => (
              <li key={idx} className="flex items-start text-slate-300">
                <span className="mr-3 text-slate-400">•</span>
                <span>{signal}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default VerdictCard;
