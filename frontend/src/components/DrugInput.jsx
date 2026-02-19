import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import { DRUG_LIST } from '../data/mockData';
import './DrugInput.css';

export default function DrugInput({ selectedDrugs, onDrugsChange, disabled }) {
  const [query, setQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  const normalizedList = useMemo(() =>
    DRUG_LIST.map(d => d.toLowerCase()).sort(),
    []
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return normalizedList.filter(d => !selectedDrugs.includes(d));
    const q = query.toLowerCase().trim();
    return normalizedList
      .filter(d => !selectedDrugs.includes(d) && d.includes(q))
      .sort((a, b) => {
        // Prefer starts-with matches
        const aStarts = a.startsWith(q) ? 0 : 1;
        const bStarts = b.startsWith(q) ? 0 : 1;
        return aStarts - bStarts || a.localeCompare(b);
      });
  }, [query, selectedDrugs, normalizedList]);

  // Clamp highlight index to filtered list bounds
  const safeHighlightIdx = Math.min(highlightIdx, Math.max(0, filtered.length - 1));

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) &&
          inputRef.current && !inputRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const addDrug = useCallback((drug) => {
    const d = drug.toLowerCase().trim();
    if (d && !selectedDrugs.includes(d)) {
      onDrugsChange([...selectedDrugs, d]);
    }
    setQuery('');
    inputRef.current?.focus();
  }, [selectedDrugs, onDrugsChange]);

  const removeDrug = useCallback((drug) => {
    onDrugsChange(selectedDrugs.filter(d => d !== drug));
  }, [selectedDrugs, onDrugsChange]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[safeHighlightIdx]) {
        addDrug(filtered[safeHighlightIdx]);
      }
    } else if (e.key === 'Backspace' && !query && selectedDrugs.length > 0) {
      removeDrug(selectedDrugs[selectedDrugs.length - 1]);
    }
  }, [filtered, safeHighlightIdx, addDrug, query, selectedDrugs, removeDrug]);

  const handlePaste = useCallback((e) => {
    const text = e.clipboardData.getData('text');
    if (text.includes(',')) {
      e.preventDefault();
      const drugs = text.split(',').map(d => d.trim().toLowerCase()).filter(Boolean);
      const validDrugs = drugs.filter(d => normalizedList.includes(d) && !selectedDrugs.includes(d));
      if (validDrugs.length > 0) {
        onDrugsChange([...selectedDrugs, ...validDrugs]);
      }
      setQuery('');
    }
  }, [normalizedList, selectedDrugs, onDrugsChange]);

  const selectAll = () => {
    onDrugsChange([...new Set([...selectedDrugs, ...normalizedList])]);
    setQuery('');
  };

  const clearAll = () => {
    onDrugsChange([]);
    setQuery('');
    inputRef.current?.focus();
  };

  return (
    <div className={`drug-input-section ${disabled ? 'drug-input-disabled' : ''}`}>
      <div className="drug-input-container">
        {/* Tags */}
        <div className="drug-tags-area" onClick={() => inputRef.current?.focus()}>
          <AnimatePresence>
            {selectedDrugs.map(drug => (
              <motion.span
                key={drug}
                className="drug-tag"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.2 }}
              >
                {drug}
                <button className="drug-tag-remove" onClick={(e) => { e.stopPropagation(); removeDrug(drug); }}>
                  <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                </button>
              </motion.span>
            ))}
          </AnimatePresence>

          <input
            ref={inputRef}
            type="text"
            className="drug-search-input"
            placeholder={selectedDrugs.length === 0 ? 'Type drug name or paste comma-separated list...' : 'Add more...'}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setHighlightIdx(0); setShowDropdown(true); }}
            onFocus={() => setShowDropdown(true)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            disabled={disabled}
          />
        </div>

        {/* Dropdown */}
        <AnimatePresence>
          {showDropdown && filtered.length > 0 && !disabled && (
            <motion.div
              ref={dropdownRef}
              className="drug-dropdown"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
            >
              <div className="drug-dropdown-scroll">
                {filtered.slice(0, 30).map((drug, idx) => (
                  <button
                    key={drug}
                    className={`drug-dropdown-item ${idx === safeHighlightIdx ? 'drug-dropdown-item--active' : ''}`}
                    onMouseEnter={() => setHighlightIdx(idx)}
                    onClick={() => { addDrug(drug); setShowDropdown(false); }}
                  >
                    {drug}
                  </button>
                ))}
                {filtered.length > 30 && (
                  <div className="drug-dropdown-more">
                    +{filtered.length - 30} more — keep typing to narrow
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Actions */}
      <div className="drug-actions">
        <button className="drug-action-btn" onClick={selectAll} disabled={disabled}>
          Select all ({normalizedList.length})
        </button>
        <button className="drug-action-btn" onClick={clearAll} disabled={disabled || selectedDrugs.length === 0}>
          Clear all
        </button>
        {selectedDrugs.length > 0 && (
          <span className="drug-count">{selectedDrugs.length} selected</span>
        )}
      </div>
    </div>
  );
}
