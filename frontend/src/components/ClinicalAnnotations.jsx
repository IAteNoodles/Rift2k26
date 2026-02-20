import { useState, useMemo } from 'react';
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import './ClinicalAnnotations.css';

const levelColors = {
  '1A': 'level-1',
  '1B': 'level-1',
  '2A': 'level-2',
  '2B': 'level-2',
  'Strong': 'level-1',
  'Moderate': 'level-2',
};

/* Derive a category from the risk label */
function deriveCategory(riskLabel) {
  const l = (riskLabel || '').toLowerCase();
  if (l === 'toxic') return 'Toxicity';
  if (l === 'adjust dosage') return 'Dosage';
  if (l === 'ineffective') return 'Efficacy';
  if (l === 'safe') return 'Dosage';
  return 'Dosage';
}

/* Build annotation rows from apiResults */
function buildAnnotations(apiResults) {
  if (!apiResults) return [];
  return apiResults.map(result => {
    const profile = result.pharmacogenomic_profile || {};
    const risk = result.risk_assessment || {};
    const rec = result.clinical_recommendation || {};
    const variants = profile.detected_variants || [];

    return {
      drug: result.drug,
      category: deriveCategory(risk.risk_label),
      gene: profile.primary_gene || '—',
      variant: variants.length > 0 ? variants[0].rsid : '—',
      diplotype: profile.diplotype || '—',
      level: rec.classification || '—',
      phenotype: profile.phenotype || '—',
      source: rec.source || null,
      guideline: rec.guideline_name || null,
    };
  });
}

export default function ClinicalAnnotations({ apiResults }) {
  const [sortByLevel, setSortByLevel] = useState(true);

  const annotations = useMemo(() => {
    let result = buildAnnotations(apiResults);

    if (sortByLevel) {
      const levelOrder = { 'Strong': 0, '1A': 0, '1B': 1, 'Moderate': 2, '2A': 2, '2B': 3 };
      result = [...result].sort((a, b) => (levelOrder[a.level] ?? 9) - (levelOrder[b.level] ?? 9));
    }

    return result;
  }, [apiResults, sortByLevel]);

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
          Evidence-based clinical annotations derived from pharmacogenomic analysis.
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
              <th>Source</th>
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
                  <span className={`evidence-badge ${levelColors[a.level] || ''}`}>
                    {a.level}
                  </span>
                </td>
                <td className="annot-phenotype">{a.phenotype}</td>
                <td className="annot-source">{a.source || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </motion.div>
    </section>
  );
}
