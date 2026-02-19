import { useState, useMemo } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import { CLINICAL_ANNOTATIONS } from '../data/mockData';
import './ClinicalAnnotations.css';

const levelColors = {
  '1A': 'level-1',
  '1B': 'level-1',
  '2A': 'level-2',
  '2B': 'level-2',
};

export default function ClinicalAnnotations({ selectedDrugs }) {
  const [sortByLevel, setSortByLevel] = useState(true);

  const annotations = useMemo(() => {
    const selected = new Set(selectedDrugs.map(d => d.toLowerCase()));
    let result = CLINICAL_ANNOTATIONS.filter(a => selected.has(a.drug.toLowerCase()));

    if (sortByLevel) {
      const levelOrder = { '1A': 0, '1B': 1, '2A': 2, '2B': 3 };
      result = [...result].sort((a, b) => (levelOrder[a.level] || 9) - (levelOrder[b.level] || 9));
    }

    return result;
  }, [selectedDrugs, sortByLevel]);

  if (annotations.length === 0) return null;

  return (
    <section id="clinical-annotations" className="annotations-section">
      <motion.h2
        className="section-heading"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.25 }}
      >
        Clinical Annotations
      </motion.h2>
      <div className="section-desc-row">
        <p className="section-desc">
          Evidence-based clinical annotations from PharmGKB for selected drugs.
        </p>
        <button
          className="sort-toggle"
          onClick={() => setSortByLevel(prev => !prev)}
        >
          {sortByLevel ? 'Sort by drug' : 'Sort by evidence'}
        </button>
      </div>

      <motion.div
        className="annotations-table-wrapper"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
      >
        <table className="annotations-table">
          <thead>
            <tr>
              <th>Drug</th>
              <th>Category</th>
              <th>Gene</th>
              <th>Variant</th>
              <th>Diplotype</th>
              <th>Evidence</th>
              <th>Phenotype</th>
              <th>PharmGKB</th>
            </tr>
          </thead>
          <tbody>
            {annotations.map((a, i) => (
              <tr key={i} className="annotation-row">
                <td className="annot-drug">{a.drug}</td>
                <td><span className={`annot-category annot-cat-${a.category.toLowerCase()}`}>{a.category}</span></td>
                <td className="annot-gene">{a.gene}</td>
                <td className="annot-variant">{a.variant}</td>
                <td className="annot-diplotype">{a.diplotype}</td>
                <td>
                  <span className={`evidence-badge ${levelColors[a.level]}`}>
                    {a.level}
                  </span>
                </td>
                <td className="annot-phenotype">{a.phenotype}</td>
                <td>
                  <a
                    href={`https://www.pharmgkb.org/guidelineAnnotation/${a.pgkbId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="pgkb-link"
                  >
                    {a.pgkbId}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </motion.div>
    </section>
  );
}
