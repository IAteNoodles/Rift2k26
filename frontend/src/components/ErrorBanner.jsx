import { useEffect } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import './ErrorBanner.css';

export default function ErrorBanner({ error, onDismiss }) {
  useEffect(() => {
    if (error) {
      const timer = setTimeout(onDismiss, 8000);
      return () => clearTimeout(timer);
    }
  }, [error, onDismiss]);

  // Determine severity from message
  const isWarning = error && (
    error.toLowerCase().includes('large') ||
    error.toLowerCase().includes('missing annotation')
  );

  return (
    <AnimatePresence>
      {error && (
        <motion.div
          className={`error-banner ${isWarning ? 'error-banner--warning' : 'error-banner--error'}`}
          initial={{ y: -60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -60, opacity: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="error-banner-inner">
            <div className="error-banner-icon">
              {isWarning ? (
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 2L1.5 16H16.5L9 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" fill="none"/>
                  <line x1="9" y1="7" x2="9" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <circle cx="9" cy="13.5" r="0.6" fill="currentColor"/>
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <circle cx="9" cy="9" r="7.5" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                  <path d="M6.5 6.5L11.5 11.5M11.5 6.5L6.5 11.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              )}
            </div>
            <p className="error-banner-message">{error}</p>
            <button className="error-banner-close" onClick={onDismiss}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
