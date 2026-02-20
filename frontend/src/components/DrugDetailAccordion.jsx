import { useState } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import './DrugDetailAccordion.css';

function riskLabelToTier(label) {
  const l = (label || '').toLowerCase();
  if (l === 'toxic' || l === 'ineffective') return 'avoid';
  if (l === 'adjust dosage' || l === 'unknown') return 'caution';
  return 'routine';
}

const tierDot = {
  avoid:   'var(--rose)',
  caution: 'var(--amber)',
  routine: 'var(--emerald)'
};

const tierLabel = {
  avoid:   'Avoid',
  caution: 'Caution',
  routine: 'Routine'
};

export default function DrugDetailAccordion({ apiResults }) {
  const [openDrug, setOpenDrug] = useState(null);

  if (!apiResults || apiResults.length === 0) return null;

  const toggle = (drug) => {
    setOpenDrug(prev => prev === drug ? null : drug);
  };

  return (
    <section id="prescribing-info" className="drug-detail-section">
      <motion.h2
        className="section-heading"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15 }}
      >
        Prescribing Information
      </motion.h2>
      <p className="section-desc">
        Expand each drug for gene-specific diplotype, phenotype, and guideline recommendations.
      </p>

      <div className="accordion-list">
        {apiResults.map((result, i) => {
          const drug = result.drug;
          const profile = result.pharmacogenomic_profile || {};
          const risk = result.risk_assessment || {};
          const rec = result.clinical_recommendation || {};
          const llm = result.llm_generated_explanation || {};
          const tier = riskLabelToTier(risk.risk_label);
          const isOpen = openDrug === drug;

          const gene = profile.primary_gene || '—';
          const diplotype = profile.diplotype || '—';
          const phenotype = profile.phenotype || '—';

          // Build guideline info from clinical_recommendation
          const guidelineSource = rec.source || '—';
          const summary = llm.summary || rec.cpic_update || 'No clinical summary available.';
          const recommendation = rec.drug_recommendation || rec.cpic_update || 'No specific recommendation available.';
          const classification = rec.classification || null;

          return (
            <motion.div
              key={drug}
              className={`accordion-item ${isOpen ? 'accordion-open' : ''}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + i * 0.04, duration: 0.35 }}
            >
              <button
                className="accordion-header"
                onClick={() => toggle(drug)}
              >
                <div className="accordion-header-left">
                  <span className="tier-dot" style={{ background: tierDot[tier] }} />
                  <span className="accordion-drug-name">{drug}</span>
                  <span className={`tier-badge tier-badge--${tier}`}>{tierLabel[tier]}</span>
                </div>
                <div className="accordion-header-right">
                  <span className="accordion-gene">{gene}</span>
                  <svg
                    className={`accordion-chevron ${isOpen ? 'accordion-chevron--open' : ''}`}
                    width="16" height="16" viewBox="0 0 16 16" fill="none"
                  >
                    <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              </button>

              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    className="accordion-body"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <div className="accordion-body-inner">
                      {/* Meta row */}
                      <div className="drug-meta-grid">
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Gene(s)</span>
                          <span className="drug-meta-value">{gene}</span>
                        </div>
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Diplotype</span>
                          <span className="drug-meta-value mono">{diplotype}</span>
                        </div>
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Phenotype</span>
                          <span className="drug-meta-value">{phenotype}</span>
                        </div>
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Risk Level</span>
                          <span className="drug-meta-value">{risk.risk_label || '—'} ({risk.severity || '—'})</span>
                        </div>
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Confidence</span>
                          <span className="drug-meta-value">{risk.confidence_score != null ? `${(risk.confidence_score * 100).toFixed(0)}%` : '—'}</span>
                        </div>
                      </div>

                      {/* Guideline */}
                      <div className="guidelines-list">
                        <div className="guideline-card">
                          <div className="guideline-source-row">
                            <span className="guideline-source">{guidelineSource}</span>
                            {classification && (
                              <span className="guideline-source" style={{ marginLeft: '8px', opacity: 0.7 }}>
                                {classification}
                              </span>
                            )}
                          </div>
                          <p className="guideline-summary">{summary}</p>
                          {rec.drug_recommendation && (
                            <div className="guideline-rec">
                              <span className="guideline-rec-label">Recommendation</span>
                              <p className="guideline-rec-text">{recommendation}</p>
                            </div>
                          )}
                          {rec.implications && Object.keys(rec.implications).length > 0 && (
                            <div className="guideline-rec">
                              <span className="guideline-rec-label">Implications</span>
                              {Object.entries(rec.implications).map(([gene, text]) => (
                                <p key={gene} className="guideline-rec-text"><strong>{gene}:</strong> {text}</p>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
