import { useState, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import { buildExportJSON } from '../data/mockData';
import './ExportBar.css';

export default function ExportBar({ selectedDrugs }) {
  const [copied, setCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const jsonString = useMemo(
    () => JSON.stringify(buildExportJSON(selectedDrugs), null, 2),
    [selectedDrugs]
  );

  const downloadJSON = useCallback(() => {
    const data = buildExportJSON(selectedDrugs);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pgx_report_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [selectedDrugs]);

  const copyToClipboard = useCallback(async () => {
    const data = buildExportJSON(selectedDrugs);
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = JSON.stringify(data, null, 2);
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [selectedDrugs]);

  return (
    <motion.div
      className="export-bar"
      initial={{ y: 60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.5, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="export-bar-inner">
        <div className="export-info">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 10L2 13C2 13.5523 2.44772 14 3 14L13 14C13.5523 14 14 13.5523 14 13L14 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M8 2L8 10M8 10L5 7M8 10L11 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>Export Results</span>
        </div>

        <div className="export-actions">
          <button className="export-btn export-btn--view" onClick={() => setShowPreview(v => !v)}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1.5 7C1.5 7 3.5 3 7 3C10.5 3 12.5 7 12.5 7C12.5 7 10.5 11 7 11C3.5 11 1.5 7 1.5 7Z" stroke="currentColor" strokeWidth="1.3" fill="none"/>
              <circle cx="7" cy="7" r="2" stroke="currentColor" strokeWidth="1.3" fill="none"/>
            </svg>
            {showPreview ? 'Hide JSON' : 'View JSON'}
          </button>
          <button className="export-btn export-btn--json" onClick={downloadJSON}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 9V12C2 12.5 2.5 13 3 13H11C11.5 13 12 12.5 12 12V9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              <path d="M7 1V9M7 9L4.5 6.5M7 9L9.5 6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Download JSON
          </button>

          <button className="export-btn export-btn--copy" onClick={copyToClipboard}>
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="4" y="4" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3" fill="none"/>
                  <path d="M10 4V3C10 2.44772 9.55228 2 9 2H3C2.44772 2 2 2.44772 2 3V9C2 9.55228 2.44772 10 3 10H4" stroke="currentColor" strokeWidth="1.3"/>
                </svg>
                Copy to Clipboard
              </>
            )}
          </button>
        </div>
      </div>

      {/* Toast */}
      <AnimatePresence>
        {copied && (
          <motion.div
            className="copy-toast"
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: -50, opacity: 1 }}
            exit={{ y: 10, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            JSON copied to clipboard
          </motion.div>
        )}
      </AnimatePresence>

      {/* JSON Preview Panel — portalled to body so it centers on the viewport */}
      {createPortal(
        <AnimatePresence>
          {showPreview && (
            <motion.div
              className="json-preview-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setShowPreview(false)}
            >
              <motion.div
                className="json-preview-panel"
                initial={{ y: 40, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 40, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="json-preview-header">
                  <span className="json-preview-title">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M4 2C3.44772 2 3 2.44772 3 3V13C3 13.5523 3.44772 14 4 14H12C12.5523 14 13 13.5523 13 13V6L9 2H4Z" stroke="currentColor" strokeWidth="1.3" fill="none"/>
                      <path d="M9 2V6H13" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
                    </svg>
                    pgx_report.json
                  </span>
                  <div className="json-preview-actions">
                    <button className="json-preview-copy" onClick={copyToClipboard}>
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                    <button className="json-preview-close" onClick={() => setShowPreview(false)}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>
                </div>
                <pre className="json-preview-body"><code>{jsonString}</code></pre>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </motion.div>
  );
}
