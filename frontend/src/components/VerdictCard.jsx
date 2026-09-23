import React from 'react';
import FormattedText, { InlineFormattedText } from './FormattedText';

const DECISION_STYLES = {
  PURSUE: {
    border: 'rgba(63, 185, 80, 0.25)',
    badgeBg: 'rgba(34, 197, 94, 0.14)',
    badgeBorder: 'rgba(63, 185, 80, 0.25)',
    badgeColor: '#3fb950',
    icon: 'ti-circle-check',
    iconColor: '#3fb950',
  },
  DEPRIORITIZE: {
    border: 'rgba(248, 81, 73, 0.25)',
    badgeBg: 'rgba(248, 81, 73, 0.12)',
    badgeBorder: 'rgba(248, 81, 73, 0.25)',
    badgeColor: '#f85149',
    icon: 'ti-circle-x',
    iconColor: '#f85149',
  },
  WATCH: {
    border: 'rgba(210, 153, 34, 0.25)',
    badgeBg: 'rgba(210, 153, 34, 0.12)',
    badgeBorder: 'rgba(210, 153, 34, 0.25)',
    badgeColor: '#d29922',
    icon: 'ti-eye',
    iconColor: '#d29922',
  },
};

function VerdictCard({ verdict, company }) {
  const decision = (verdict?.decision || 'WATCH').toUpperCase();
  const styles = DECISION_STYLES[decision] || DECISION_STYLES.WATCH;

  return (
    <div style={{ border: `1px solid ${styles.border}`, borderRadius: 'var(--border-radius-md)', background: 'var(--color-background-secondary)', padding: '1.5rem', boxShadow: '0 18px 50px rgba(0, 0, 0, 0.18)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
            Sales verdict
          </p>
          <h2 style={{ fontSize: 26, fontWeight: 700, color: 'var(--color-text-primary)', margin: 0, lineHeight: 1.1 }}>{company}</h2>
        </div>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '9px 14px', borderRadius: 999, background: styles.badgeBg, border: `1px solid ${styles.badgeBorder}` }}>
          <i className={`ti ${styles.icon}`} style={{ fontSize: 14, color: styles.iconColor }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: styles.badgeColor }}>{decision}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '1rem', color: 'var(--color-text-secondary)', fontSize: 13 }}>
        <span>Confidence</span>
        <strong className={`confidence confidence-${verdict?.confidence || 'unknown'}`}>{verdict?.confidence || 'unknown'}</strong>
      </div>

      {verdict?.reasoning && (
        <div style={{ padding: '1.1rem 1.1rem 0.9rem', borderRadius: 'var(--border-radius-md)', background: 'rgba(255, 255, 255, 0.02)', marginBottom: '1.25rem' }}>
          <FormattedText text={verdict.reasoning} accentColor={styles.iconColor} />
        </div>
      )}

      {verdict?.next_step && (
        <div className="next-step"><strong>Recommended next step</strong><span>{verdict.next_step}</span></div>
      )}

      {verdict?.signals?.length > 0 && (
        <div>
          <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: '0.75rem' }}>Key signals</p>
          <div style={{ display: 'grid', gap: 10 }}>
            {verdict.signals.map((signal, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: styles.iconColor, marginTop: 6, flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
                  <InlineFormattedText text={signal} />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default VerdictCard;
