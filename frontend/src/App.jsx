import { useState, useCallback, useRef, useEffect } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './components/Sidebar';
import FileUpload from './components/FileUpload';
import DrugInput from './components/DrugInput';
import RiskSummary from './components/RiskSummary';
import DrugDetailAccordion from './components/DrugDetailAccordion';
import PhenotypeGrid from './components/PhenotypeGrid';
import ClinicalAnnotations from './components/ClinicalAnnotations';
import ExportBar from './components/ExportBar';
import ErrorBanner from './components/ErrorBanner';
import './App.css';

const API_URL = '/api';

/*
  State machine: idle → fileUploaded → drugsSelected → analyzing → results
  Transitions:
    - File accepted → fileUploaded
    - File removed  → idle
    - Drug selected (first) → drugsSelected
    - Drug cleared  → fileUploaded
    - Analyze click → analyzing → results
    - Reset → idle
*/

function getAppState(file, selectedDrugs, analyzing, hasResults) {
  if (hasResults) return 'results';
  if (analyzing) return 'analyzing';
  if (selectedDrugs.length > 0 && file) return 'drugsSelected';
  if (file) return 'fileUploaded';
  return 'idle';
}

const ANALYSIS_STEPS = [
  { label: 'Uploading VCF file to server…', duration: 2500 },
  { label: 'Validating variant call format…', duration: 2000 },
  { label: 'Running PharmCAT genotype caller…', duration: 8000 },
  { label: 'Extracting diplotype calls…', duration: 4000 },
  { label: 'Mapping gene–drug interactions (CPIC)…', duration: 5000 },
  { label: 'Computing risk profiles…', duration: 4000 },
  { label: 'Generating LLM-enriched clinical report…', duration: 12000 },
  { label: 'Assembling final results…', duration: 3000 },
];

function AnalysisSteps({ active }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!active) {
      // reset on next tick to avoid sync setState in effect body
      const reset = setTimeout(() => setCurrentStep(0), 0);
      return () => clearTimeout(reset);
    }
    let idx = 0;
    const advance = () => {
      if (idx < ANALYSIS_STEPS.length - 1) {
        idx += 1;
        setCurrentStep(idx);
        timer = setTimeout(advance, ANALYSIS_STEPS[idx].duration);
      }
    };
    let timer = setTimeout(advance, ANALYSIS_STEPS[0].duration);
    return () => clearTimeout(timer);
  }, [active]);

  if (!active) return null;

  return (
    <div className="analysis-steps">
      {ANALYSIS_STEPS.map((step, i) => {
        const state = i < currentStep ? 'done' : i === currentStep ? 'active' : 'pending';
        return (
          <motion.div
            key={i}
            className={`analysis-step analysis-step--${state}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: state === 'pending' ? 0.35 : 1, x: 0 }}
            transition={{ duration: 0.35, delay: i * 0.06 }}
          >
            <span className="analysis-step-icon">
              {state === 'done' ? (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7.5L5.5 10L11 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              ) : state === 'active' ? (
                <span className="analysis-step-pulse" />
              ) : (
                <span className="analysis-step-dot" />
              )}
            </span>
            <span className="analysis-step-label">{step.label}</span>
          </motion.div>
        );
      })}
    </div>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [selectedDrugs, setSelectedDrugs] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [hasResults, setHasResults] = useState(false);
  const [apiResults, setApiResults] = useState(null);
  const [error, setError] = useState(null);
  const [supportedDrugs, setSupportedDrugs] = useState([]);
  const [backendReady, setBackendReady] = useState(false);
  const resultsRef = useRef(null);

  const appState = getAppState(file, selectedDrugs, analyzing, hasResults);

  // Fetch supported drugs from backend /health on mount
  useEffect(() => {
    let cancelled = false;
    async function fetchSupportedDrugs() {
      try {
        const res = await fetch(`${API_URL}/health`);
        if (!res.ok) throw new Error(`Health check failed (${res.status})`);
        const data = await res.json();
        if (!cancelled) {
          setSupportedDrugs(data.supported_drugs || []);
          setBackendReady(true);
        }
      } catch {
        if (!cancelled) {
          setError('Unable to connect to analysis server. Please ensure the backend is running on ' + API_URL);
          setBackendReady(false);
        }
      }
    }
    fetchSupportedDrugs();
    return () => { cancelled = true; };
  }, []);

  const handleFileAccept = useCallback((f) => {
    setFile(f);
    setError(null);
    setHasResults(false);
  }, []);

  const handleFileRemove = useCallback(() => {
    setFile(null);
    setSelectedDrugs([]);
    setHasResults(false);
    setApiResults(null);
  }, []);

  const handleDrugsChange = useCallback((drugs) => {
    setSelectedDrugs(drugs);
    if (hasResults) setHasResults(false);
  }, [hasResults]);

  const handleAnalyze = useCallback(async () => {
    if (!file || selectedDrugs.length === 0) return;
    setAnalyzing(true);
    setHasResults(false);
    setApiResults(null);
    setError(null);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 min timeout

    try {
      const formData = new FormData();
      formData.append('file', file.raw, file.name);
      formData.append('drugs', JSON.stringify(selectedDrugs));

      const res = await fetch(`${API_URL}/analyze/upload`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      if (!res.ok) {
        let detail;
        try {
          const errBody = await res.json();
          // FastAPI returns detail as string (custom HTTPException) or array (validation error)
          if (typeof errBody.detail === 'string') {
            detail = errBody.detail;
          } else if (Array.isArray(errBody.detail)) {
            detail = errBody.detail.map(e => `${e.loc?.join(' → ') || ''}: ${e.msg || ''}`).join('; ');
          } else if (errBody.detail) {
            detail = JSON.stringify(errBody.detail);
          }
        } catch {
          // response wasn't JSON (e.g. proxy HTML error)
        }

        if (res.status === 504) {
          throw new Error('Analysis timed out. The VCF file may be too large or PharmCAT is unavailable.');
        } else if (res.status === 422) {
          throw new Error(detail || 'Analysis pipeline failed. This may indicate a missing API key or model coercion error on the server.');
        } else if (res.status === 400) {
          throw new Error(detail || 'Invalid request. Please check the selected drugs and VCF file.');
        } else if (res.status === 500) {
          throw new Error(detail || 'Internal server error. Please check backend logs.');
        } else {
          throw new Error(detail || `Server error (${res.status})`);
        }
      }

      const data = await res.json();
      setApiResults(data);
      setHasResults(true);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Analysis timed out after 5 minutes. Please try with a smaller VCF file.');
      } else if (err.message === 'Failed to fetch' || err.message === 'NetworkError when attempting to fetch resource.') {
        setError('Cannot reach the analysis server. Please ensure the backend is running.');
      } else {
        setError(err.message || 'Analysis failed. Please try again.');
      }
    } finally {
      clearTimeout(timeoutId);
      setAnalyzing(false);
    }
  }, [file, selectedDrugs]);

  const handleReset = useCallback(() => {
    setFile(null);
    setSelectedDrugs([]);
    setAnalyzing(false);
    setHasResults(false);
    setApiResults(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const handleError = useCallback((msg) => {
    setError(msg);
  }, []);

  const dismissError = useCallback(() => {
    setError(null);
  }, []);

  const canAnalyze = file && selectedDrugs.length > 0 && !analyzing && !hasResults;

  return (
    <div className="app-layout">
      <Sidebar appState={appState} />

      <main className="main-content">
        <ErrorBanner error={error} onDismiss={dismissError} />

        <div className="content-wrapper">
          {/* Hero */}
          <motion.header
            className="hero"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <h1 className="hero-title">
              Pharmacogenomic <span className="hero-accent">Risk Assessment</span>
            </h1>
            <p className="hero-subtitle">
              Upload a patient VCF file, select medications, and receive genotype-guided prescribing recommendations powered by clinical pharmacogenomics guidelines.
            </p>
          </motion.header>

          {/* Step 1: File Upload */}
          <motion.section
            className="step-section"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5 }}
          >
            <div className="step-header">
              <span className="step-number">1</span>
              <div>
                <h2 className="step-title">Upload VCF File</h2>
                <p className="step-desc">Drag and drop or browse for a VCF file containing patient variant data</p>
              </div>
            </div>
            <FileUpload
              file={file}
              onFileAccept={handleFileAccept}
              onFileRemove={handleFileRemove}
              onError={handleError}
            />
          </motion.section>

          {/* Step 2: Drug Selection */}
          <motion.section
            className={`step-section ${!file ? 'step-section--disabled' : ''}`}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: file ? 1 : 0.4, y: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
          >
            <div className="step-header">
              <span className="step-number">2</span>
              <div>
                <h2 className="step-title">Select Medications</h2>
                <p className="step-desc">Search and select drugs to assess, or paste a comma-separated list</p>
              </div>
            </div>
            <DrugInput
              selectedDrugs={selectedDrugs}
              onDrugsChange={handleDrugsChange}
              disabled={!file || !backendReady}
              drugList={supportedDrugs}
            />
          </motion.section>

          {/* Analyze Button */}
          <AnimatePresence>
            {(canAnalyze || analyzing) && (
              <motion.div
                className="analyze-row"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ duration: 0.3 }}
              >
                <button
                  className={`analyze-btn ${analyzing ? 'analyze-btn--loading' : ''}`}
                  onClick={handleAnalyze}
                  disabled={analyzing}
                >
                  {analyzing ? (
                    <>
                      <span className="analyze-spinner" />
                      Analyzing genotype data...
                    </>
                  ) : (
                    <>
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                        <path d="M9 5V9L12 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      Analyze {selectedDrugs.length} Drug{selectedDrugs.length !== 1 ? 's' : ''}
                    </>
                  )}
                </button>
                <AnalysisSteps active={analyzing} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results */}
          <AnimatePresence>
            {hasResults && (
              <motion.div
                ref={resultsRef}
                className="results-panel"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4 }}
              >
                <div className="results-divider">
                  <span>Analysis Results</span>
                </div>

                <RiskSummary apiResults={apiResults} />
                <DrugDetailAccordion apiResults={apiResults} />
                <PhenotypeGrid apiResults={apiResults} />
                <ClinicalAnnotations apiResults={apiResults} />

                {/* Reset */}
                <div className="reset-row">
                  <button className="reset-btn" onClick={handleReset}>
                    Start New Analysis
                  </button>
                </div>

                <ExportBar apiResults={apiResults} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
