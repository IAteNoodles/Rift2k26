// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import './RiskSummary.css';

/* Map backend risk_label to a 3-tier classification */
function riskLabelToTier(label) {
  const l = (label || '').toLowerCase();
  if (l === 'toxic' || l === 'ineffective') return 'avoid';
  if (l === 'adjust dosage' || l === 'unknown') return 'caution';
  return 'routine'; // "Safe" and anything else
}

const TIER_DESCRIPTIONS = {
  avoid: "These drugs should be avoided based on the patient's genetic profile. Alternative medications are strongly recommended.",
  caution: 'Dose adjustments or enhanced monitoring may be required. Consult prescribing guidelines.',
  routine: 'No pharmacogenomic-based prescribing changes are recommended. Standard dosing applies.',
};

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

export default function RiskSummary({ apiResults }) {
  if (!apiResults || apiResults.length === 0) return null;

  // Classify drugs into tiers from real API data
  const tiers = { avoid: [], caution: [], routine: [] };
  apiResults.forEach(result => {
    const tier = riskLabelToTier(result.risk_assessment?.risk_label);
    tiers[tier].push(result.drug);
  });

  const totalDrugs = apiResults.length;

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
        Drug classification based on {totalDrugs} selected medication{totalDrugs !== 1 ? 's' : ''} and patient genotype.
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

              <p className="risk-card-desc">{TIER_DESCRIPTIONS[tier]}</p>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
