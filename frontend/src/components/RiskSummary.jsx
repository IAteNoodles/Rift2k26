// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import { RISK_TIERS, getDrugRiskTier } from '../data/mockData';
import './RiskSummary.css';

const tierConfig = {
  avoid:   {
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <path d="M11 2L2 20H20L11 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
        <line x1="11" y1="9" x2="11" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="11" cy="16" r="0.8" fill="currentColor"/>
      </svg>
    ),
    label: 'Avoid Use',
    gradient: 'linear-gradient(135deg, #FEF2F2, #FEE2E2)',
    borderColor: 'var(--rose)',
    textColor: 'var(--rose)',
    bgColor: 'var(--rose-bg)'
  },
  caution: {
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <circle cx="11" cy="11" r="9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
        <path d="M11 7V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="11" cy="15" r="0.8" fill="currentColor"/>
      </svg>
    ),
    label: 'Use with Caution',
    gradient: 'linear-gradient(135deg, #FFFBEB, #FEF3C7)',
    borderColor: 'var(--amber)',
    textColor: 'var(--amber)',
    bgColor: 'var(--amber-bg)'
  },
  routine: {
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <circle cx="11" cy="11" r="9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
        <path d="M7 11L10 14L15 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    label: 'Routine Use',
    gradient: 'linear-gradient(135deg, #ECFDF5, #D1FAE5)',
    borderColor: 'var(--emerald)',
    textColor: 'var(--emerald)',
    bgColor: 'var(--emerald-bg)'
  }
};

export default function RiskSummary({ selectedDrugs }) {
  // Classify selected drugs into tiers
  const tiers = { avoid: [], caution: [], routine: [] };
  selectedDrugs.forEach(drug => {
    const tier = getDrugRiskTier(drug);
    tiers[tier].push(drug);
  });

  return (
    <section id="risk-summary" className="risk-summary">
      <motion.h2
        className="section-heading"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        Risk Assessment Summary
      </motion.h2>
      <p className="section-desc">
        Drug classification based on {selectedDrugs.length} selected medication{selectedDrugs.length !== 1 ? 's' : ''} and patient genotype.
      </p>

      <div className="risk-cards">
        {['avoid', 'caution', 'routine'].map((tier, i) => {
          const cfg = tierConfig[tier];
          const drugs = tiers[tier];
          return (
            <motion.div
              key={tier}
              className="risk-card"
              style={{
                background: cfg.gradient,
                borderLeftColor: cfg.borderColor
              }}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="risk-card-header">
                <div className="risk-card-icon" style={{ color: cfg.textColor }}>
                  {cfg.icon}
                </div>
                <div>
                  <h3 className="risk-card-title" style={{ color: cfg.textColor }}>
                    {cfg.label}
                  </h3>
                  <span className="risk-card-count" style={{ color: cfg.textColor }}>
                    {drugs.length} drug{drugs.length !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>

              {drugs.length > 0 ? (
                <div className="risk-card-drugs">
                  {drugs.map(drug => (
                    <span key={drug} className="risk-drug-chip" style={{
                      background: `color-mix(in srgb, ${cfg.borderColor} 20%, transparent)`,
                      color: cfg.textColor
                    }}>
                      {drug}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="risk-card-empty">No drugs in this category</p>
              )}

              <p className="risk-card-desc">{RISK_TIERS[tier].description}</p>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
