import React, { useState } from 'react';

function EvidencePanel({ evidence }) {
  const [expandedSection, setExpandedSection] = useState(null);

  const sections = [
    { id: 'crunchbase', title: 'Crunchbase', icon: '💰' },
    { id: 'builtwith', title: 'BuiltWith', icon: '⚙️' },
    { id: 'careers', title: 'Careers Page', icon: '👥' },
    { id: 'web_search', title: 'Web Search', icon: '🔍' },
  ];

  const toggleSection = (id) => {
    setExpandedSection(expandedSection === id ? null : id);
  };

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-white mb-4">Supporting Evidence</h3>

      {sections.map((section) => (
        <div
          key={section.id}
          className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden"
        >
          <button
            onClick={() => toggleSection(section.id)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-700/50 transition"
          >
            <div className="flex items-center space-x-3">
              <span className="text-xl">{section.icon}</span>
              <span className="font-semibold text-white">{section.title}</span>
            </div>
            <span className={`text-slate-400 transition ${expandedSection === section.id ? 'rotate-180' : ''}`}>
              ▼
            </span>
          </button>

          {expandedSection === section.id && (
            <div className="border-t border-slate-700 px-6 py-4 bg-slate-900/50">
              <p className="text-slate-300 text-sm leading-relaxed">
                {evidence[section.id] || 'No data available'}
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default EvidencePanel;
