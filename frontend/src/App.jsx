import { useState, useCallback, useRef } from 'react';
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

/*
  State machine: idle → fileUploaded → drugsSelected → analyzing → results
  Transitions:
    - File accepted → fileUploaded
    - File removed  → idle
    - Drug selected (first) → drugsSelected
    - Drug cleared  → fileUploaded
    - Analyze click → analyzing (1.5s fake) → results
    - Reset → idle
*/

function getAppState(file, selectedDrugs, analyzing, hasResults) {
  if (hasResults) return 'results';
  if (analyzing) return 'analyzing';
  if (selectedDrugs.length > 0 && file) return 'drugsSelected';
  if (file) return 'fileUploaded';
  return 'idle';
}

export default function App() {
  const [file, setFile] = useState(null);
  const [selectedDrugs, setSelectedDrugs] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [hasResults, setHasResults] = useState(false);
  const [apiResults, setApiResults] = useState(null);
  const [error, setError] = useState(null);
  const resultsRef = useRef(null);

  const appState = getAppState(file, selectedDrugs, analyzing, hasResults);

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

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('drugs', selectedDrugs.join(','));

      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `Server error (${res.status})`);
      }

      const data = await res.json();
      setApiResults(data);
      setHasResults(true);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err) {
      setError(err.message || 'Analysis failed. Please try again.');
    } finally {
      setAnalyzing(false);
    }
  }, [file, selectedDrugs]);

  const handleReset = useCallback(() => {
    setFile(null);
    setSelectedDrugs([]);
    setAnalyzing(false);
    setHasResults(false);
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
              disabled={!file}
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

                <RiskSummary selectedDrugs={selectedDrugs} />
                <DrugDetailAccordion selectedDrugs={selectedDrugs} />
                <PhenotypeGrid selectedDrugs={selectedDrugs} />
                <ClinicalAnnotations selectedDrugs={selectedDrugs} />

                {/* Reset */}
                <div className="reset-row">
                  <button className="reset-btn" onClick={handleReset}>
                    Start New Analysis
                  </button>
                </div>

                <ExportBar selectedDrugs={selectedDrugs} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
