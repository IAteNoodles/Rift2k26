import { useState } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import { getDrugInfo, getDrugRiskTier } from '../data/mockData';
import './DrugDetailAccordion.css';

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

export default function DrugDetailAccordion({ selectedDrugs }) {
  const [openDrug, setOpenDrug] = useState(null);

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
        {selectedDrugs.map((drug, i) => {
          const info = getDrugInfo(drug);
          const tier = getDrugRiskTier(drug);
          const isOpen = openDrug === drug;

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
                  <span className="accordion-gene">{info.gene}</span>
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
                          <span className="drug-meta-value">{info.gene}</span>
                        </div>
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Diplotype</span>
                          <span className="drug-meta-value mono">{info.diplotype}</span>
                        </div>
                        <div className="drug-meta-item">
                          <span className="drug-meta-label">Phenotype</span>
                          <span className="drug-meta-value">{info.phenotype}</span>
                        </div>
                      </div>

                      {/* Guidelines */}
                      <div className="guidelines-list">
                        {info.guidelines.map((gl, idx) => (
                          <div key={idx} className="guideline-card">
                            <div className="guideline-source-row">
                              <span className="guideline-source">{gl.source}</span>
                              <a href={gl.url} target="_blank" rel="noopener noreferrer" className="guideline-link">
                                PharmGKB →
                              </a>
                            </div>
                            <p className="guideline-summary">{gl.summary}</p>
                            <div className="guideline-rec">
                              <span className="guideline-rec-label">Recommendation</span>
                              <p className="guideline-rec-text">{gl.recommendation}</p>
                            </div>
                          </div>
                        ))}
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
