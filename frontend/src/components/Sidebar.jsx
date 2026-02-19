// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import './Sidebar.css';

const steps = [
  { num: 1, label: 'Upload VCF', key: 'upload' },
  { num: 2, label: 'Select Drugs', key: 'drugs' },
  { num: 3, label: 'View Results', key: 'results' },
];

const sectionLinks = [
  { label: 'Risk Summary', anchor: 'risk-summary' },
  { label: 'Prescribing Info', anchor: 'prescribing-info' },
  { label: 'Phenotype Grid', anchor: 'phenotype-grid' },
  { label: 'Annotations', anchor: 'clinical-annotations' },
];

function getStepState(stepKey, appState) {
  const flow = ['idle', 'fileUploaded', 'drugsSelected', 'analyzing', 'results'];
  const stepToState = { upload: 'fileUploaded', drugs: 'drugsSelected', results: 'results' };
  const currentIdx = flow.indexOf(appState);
  const targetIdx = flow.indexOf(stepToState[stepKey]);

  if (currentIdx >= targetIdx) return 'completed';
  if (currentIdx === targetIdx - 1) return 'active';
  return 'pending';
}

export default function Sidebar({ appState }) {
  const showSections = appState === 'results';

  return (
    <aside className="sidebar">
      {/* Noise texture overlay */}
      <div className="sidebar-noise" />

      <motion.div
        className="sidebar-inner"
        initial={{ x: -20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-icon">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path d="M14 2C14 2 8 6 8 14C8 22 14 26 14 26" stroke="#14B8A6" strokeWidth="2" strokeLinecap="round"/>
              <path d="M14 2C14 2 20 6 20 14C20 22 14 26 14 26" stroke="#14B8A6" strokeWidth="2" strokeLinecap="round"/>
              <line x1="9" y1="8" x2="19" y2="8" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
              <line x1="8.5" y1="14" x2="19.5" y2="14" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round"/>
              <line x1="9" y1="20" x2="19" y2="20" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
            </svg>
          </div>
          <div>
            <h1 className="logo-text">Rift PGx</h1>
            <span className="logo-sub">Pharmacogenomics</span>
          </div>
        </div>

        {/* Step Progress */}
        <nav className="sidebar-steps">
          <span className="sidebar-section-label">Workflow</span>
          {steps.map((step, i) => {
            const state = getStepState(step.key, appState);
            return (
              <motion.div
                key={step.key}
                className={`step-item step-${state}`}
                initial={{ x: -10, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: 0.15 + i * 0.08, duration: 0.4 }}
              >
                <div className="step-indicator">
                  {state === 'completed' ? (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  ) : (
                    <span>{step.num}</span>
                  )}
                </div>
                <span className="step-label">{step.label}</span>
              </motion.div>
            );
          })}
        </nav>

        {/* Section Links (results only) */}
        {showSections && (
          <motion.nav
            className="sidebar-sections"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            <span className="sidebar-section-label">Sections</span>
            {sectionLinks.map(link => (
              <a
                key={link.anchor}
                href={`#${link.anchor}`}
                className="section-link"
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(link.anchor)?.scrollIntoView({ behavior: 'smooth' });
                }}
              >
                {link.label}
              </a>
            ))}
          </motion.nav>
        )}

        {/* Footer info */}
        <div className="sidebar-footer">
          <p>PAnno v0.3.1</p>
          <p>Sample: HG00096</p>
          <p>GRCh38</p>
        </div>
      </motion.div>
    </aside>
  );
}
