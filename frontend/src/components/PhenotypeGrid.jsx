// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import { PHENOTYPE_PREDICTIONS } from '../data/mockData';
import './PhenotypeGrid.css';

const indicators = {
  normal:    { symbol: '◎', label: 'Normal',    className: 'pheno-normal' },
  increased: { symbol: '↑',  label: 'Increased', className: 'pheno-increased' },
  decreased: { symbol: '↓',  label: 'Decreased', className: 'pheno-decreased' },
  na:        { symbol: '—',  label: 'N/A',       className: 'pheno-na' },
};

const columns = ['toxicity', 'dosage', 'efficacy', 'metabolism'];

export default function PhenotypeGrid({ selectedDrugs }) {
  const drugsWithPredictions = selectedDrugs.filter(
    d => PHENOTYPE_PREDICTIONS[d.toLowerCase()]
  );

  if (drugsWithPredictions.length === 0) return null;

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
            {drugsWithPredictions.map(drug => {
              const pred = PHENOTYPE_PREDICTIONS[drug.toLowerCase()];
              return (
                <tr key={drug} className="pheno-row">
                  <td className="pheno-td-drug">{drug}</td>
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
