// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import './PhenotypeGrid.css';

const indicators = {
  normal:    { symbol: '◎', label: 'Normal',    className: 'pheno-normal' },
  increased: { symbol: '↑',  label: 'Increased', className: 'pheno-increased' },
  decreased: { symbol: '↓',  label: 'Decreased', className: 'pheno-decreased' },
  na:        { symbol: '—',  label: 'N/A',       className: 'pheno-na' },
};

const columns = ['toxicity', 'dosage', 'efficacy', 'metabolism'];

/* Derive phenotype prediction from backend result */
function derivePrediction(result) {
  const riskLabel = (result.risk_assessment?.risk_label || '').toLowerCase();
  const phenotype = (result.pharmacogenomic_profile?.phenotype || '').toLowerCase();

  // Toxicity
  let toxicity = 'normal';
  if (riskLabel === 'toxic') toxicity = 'increased';

  // Dosage
  let dosage = 'normal';
  if (riskLabel === 'adjust dosage') dosage = 'decreased';

  // Efficacy
  let efficacy = 'normal';
  if (riskLabel === 'ineffective') efficacy = 'decreased';

  // Metabolism — based on phenotype
  let metabolism = 'normal';
  if (phenotype.includes('poor') || phenotype === 'pm') metabolism = 'decreased';
  else if (phenotype.includes('intermediate') || phenotype === 'im') metabolism = 'decreased';
  else if (phenotype.includes('rapid') || phenotype === 'rm') metabolism = 'increased';
  else if (phenotype.includes('ultrarapid') || phenotype === 'urm') metabolism = 'increased';
  else if (phenotype === 'unknown' || phenotype === 'indeterminate' || !phenotype) metabolism = 'na';

  return { toxicity, dosage, efficacy, metabolism };
}

export default function PhenotypeGrid({ apiResults }) {
  if (!apiResults || apiResults.length === 0) return null;

  return (
    <section id="phenotype-grid" className="phenotype-section">
      <motion.h2
        className="section-heading"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        Phenotype Prediction
      </motion.h2>
      <p className="section-desc">
        Predicted pharmacological impact across four dimensions for each drug.
      </p>

      {/* Legend */}
      <div className="pheno-legend">
        {Object.entries(indicators).map(([key, val]) => (
          <span key={key} className="pheno-legend-item">
            <span className={`pheno-indicator ${val.className}`}>{val.symbol}</span>
            {val.label}
          </span>
        ))}
      </div>

      <motion.div
        className="pheno-table-wrapper"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
      >
        <table className="pheno-table">
          <thead>
            <tr>
              <th className="pheno-th-drug">Drug</th>
              {columns.map(col => (
                <th key={col} className="pheno-th">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {apiResults.map(result => {
              const pred = derivePrediction(result);
              return (
                <tr key={result.drug} className="pheno-row">
                  <td className="pheno-td-drug">{result.drug}</td>
                  {columns.map(col => {
                    const val = pred[col] || 'na';
                    const ind = indicators[val];
                    return (
                      <td key={col} className="pheno-td">
                        <span className={`pheno-indicator ${ind.className}`} title={ind.label}>
                          {ind.symbol}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </motion.div>
    </section>
  );
}
