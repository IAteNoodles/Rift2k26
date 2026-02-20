import { useRef, useState, useCallback } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import './FileUpload.css';

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function sizeColor(bytes) {
  if (bytes <= 5 * 1024 * 1024) return 'emerald';
  return 'rose';
}

export default function FileUpload({ file, onFileAccept, onFileRemove, onError }) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [validating, setValidating] = useState(false);

  const validateVCF = useCallback(async (f) => {
    // Extension check
    if (!f.name.toLowerCase().endsWith('.vcf')) {
      onError('Invalid file type. Please upload a file with a .vcf extension.');
      return false;
    }

    // Size warning (still allow)
    if (f.size > 50 * 1024 * 1024) {
      onError('This file is very large (>50 MB). Processing may take longer than expected.');
    }

    // Read first chunk to verify VCF header
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const header = e.target.result;
        if (!header.startsWith('##fileformat=VCF')) {
          onError('This doesn\'t appear to be a valid VCF file. Expected header: ##fileformat=VCF');
          resolve(false);
        } else {
          resolve(true);
        }
      };
      reader.onerror = () => {
        onError('Failed to read file. Please try again.');
        resolve(false);
      };
      reader.readAsText(f.slice(0, 1024));
    });
  }, [onError]);

  const handleFile = useCallback(async (f) => {
    setValidating(true);
    const valid = await validateVCF(f);
    setValidating(false);
    if (valid) {
      // Count lines (estimate variants) from a larger chunk
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target.result;
        const lines = text.split('\n');
        const dataLines = lines.filter(l => l.length > 0 && !l.startsWith('#'));
        onFileAccept({
          raw: f,
          name: f.name,
          size: f.size,
          variantEstimate: dataLines.length,
          headerValid: true
        });
      };
      reader.readAsText(f.slice(0, 512 * 1024)); // Read up to 512KB for variant count
    }
  }, [validateVCF, onFileAccept]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const onDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => setDragOver(false), []);

  const onInputChange = useCallback((e) => {
    const f = e.target.files[0];
    if (f) handleFile(f);
    e.target.value = '';
  }, [handleFile]);

  return (
    <div className="file-upload-section">
      <AnimatePresence mode="wait">
        {!file ? (
          <motion.div
            key="dropzone"
            className={`dropzone ${dragOver ? 'dropzone-active' : ''} ${validating ? 'dropzone-validating' : ''}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => inputRef.current?.click()}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.35 }}
          >
            {/* Full-area drag overlay */}
            <AnimatePresence>
              {dragOver && (
                <motion.div
                  className="dropzone-overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="dropzone-overlay-ring">
                    <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                      <path d="M16 24L24 18L32 24" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <line x1="24" y1="19" x2="24" y2="34" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    <span>Drop to upload</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <input
              ref={inputRef}
              type="file"
              accept=".vcf"
              onChange={onInputChange}
              hidden
            />

            <div className="dropzone-icon">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <rect x="8" y="6" width="24" height="28" rx="3" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                <path d="M14 18L20 13L26 18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <line x1="20" y1="14" x2="20" y2="26" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                <line x1="14" y1="30" x2="26" y2="30" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>

            <div className="dropzone-text">
              <p className="dropzone-heading">
                {validating ? 'Validating...' : 'Drop your VCF file here'}
              </p>
              <p className="dropzone-sub">
                or <span className="dropzone-browse">browse files</span> &middot; .vcf format only
              </p>
            </div>

            <div className="dropzone-size-hint">
              <span className="size-dot size-dot--emerald" />{'≤ 5 MB — recommended'}
              <span className="size-dot size-dot--rose" style={{ marginLeft: 12 }} />{'> 5 MB — may slow processing'}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="file-card"
            className="file-card"
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className={`file-card-icon ${file.size > 5 * 1024 * 1024 ? 'file-card-icon--warning' : ''}`}>
              {file.size > 5 * 1024 * 1024 ? (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M12 9V13" stroke="var(--rose)" strokeWidth="2" strokeLinecap="round"/>
                  <circle cx="12" cy="16" r="1" fill="var(--rose)"/>
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="var(--rose)" strokeWidth="1.5" fill="none"/>
                </svg>
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M9 12L11 14L15 10" stroke="var(--emerald)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="12" cy="12" r="9" stroke="var(--emerald)" strokeWidth="1.5" fill="none"/>
                </svg>
              )}
            </div>
            <div className="file-card-info">
              <p className="file-card-name">{file.name}</p>
              {file.size > 5 * 1024 * 1024 && (
                <p className="file-card-warning">
                  File exceeds 5 MB — processing may be slower
                </p>
              )}
              <p className="file-card-meta">
                <span className={`size-badge size-badge--${sizeColor(file.size)}`}>
                  {formatSize(file.size)}
                </span>
                {file.variantEstimate > 0 && (
                  <span className="variant-badge">
                    ~{file.variantEstimate} variants
                  </span>
                )}
                <span className="valid-badge">VCF validated</span>
              </p>
            </div>
            <button
              className="file-card-remove"
              onClick={onFileRemove}
              title="Remove file"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M5 5L13 13M13 5L5 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
