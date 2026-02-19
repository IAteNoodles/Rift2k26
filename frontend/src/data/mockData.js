/*
  Mock data modeled after real HG00096 PAnno output.
  This mirrors the structure a backend API would return.
*/

export const DRUG_LIST = [
  'amitriptyline','aripiprazole','atomoxetine','brexpiprazole',
  'capecitabine','celecoxib','citalopram','clomipramine',
  'clopidogrel','codeine','desipramine','dexlansoprazole',
  'doxepin','efavirenz','escitalopram','flecainide',
  'fluorouracil','flurbiprofen','fluvoxamine','fosphenytoin',
  'hydrocodone','ibuprofen','imipramine','lansoprazole',
  'lornoxicam','meloxicam','methadone','nortriptyline',
  'omeprazole','ondansetron','oxycodone','pantoprazole',
  'paroxetine','phenytoin','pimozide','piroxicam',
  'propafenone','rabeprazole','sertraline','simvastatin',
  'tacrolimus','tamoxifen','tenoxicam','tramadol',
  'trimipramine','tropisetron','venlafaxine','voriconazole',
  'warfarin','atorvastatin','lovastatin','pitavastatin',
  'pravastatin','rosuvastatin','fluvastatin','metoprolol'
];

export const SAMPLE_DIPLOTYPES = {
  CYP2B6:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  CYP2C8:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  CYP2C9:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  CYP2C19: { diplotype: '*38/*38', phenotype: 'Indeterminate' },
  CYP2D6:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  CYP3A4:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  CYP3A5:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  CYP4F2:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  DPYD:    { diplotype: 'Ref/Ref', phenotype: 'Normal Metabolizer' },
  NUDT15:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  SLCO1B1: { diplotype: '*1/*1',  phenotype: 'Normal Function' },
  TPMT:    { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  UGT1A1:  { diplotype: '*1/*1',  phenotype: 'Normal Metabolizer' },
  VKORC1:  { diplotype: 'rs9923231 C/C', phenotype: 'Warfarin Low Sensitivity' },
  RYR1:    { diplotype: 'Reference/Reference', phenotype: 'Uncertain Susceptibility' },
  CACNA1S: { diplotype: 'Reference/Reference', phenotype: 'Uncertain Susceptibility' },
  G6PD:    { diplotype: 'B (wildtype)/B (wildtype)', phenotype: 'Normal' },
};

// 3-tier drug risk classification
export const RISK_TIERS = {
  avoid: {
    label: 'Avoid Use',
    color: 'rose',
    drugs: ['fluorouracil', 'capecitabine'],
    description: 'These drugs should be avoided based on the patient\'s genetic profile. Alternative medications are strongly recommended.'
  },
  caution: {
    label: 'Use with Caution',
    color: 'amber',
    drugs: ['fosphenytoin', 'phenytoin', 'tacrolimus', 'warfarin'],
    description: 'Dose adjustments or enhanced monitoring may be required. Consult prescribing guidelines.'
  },
  routine: {
    label: 'Routine Use',
    color: 'emerald',
    drugs: [
      'amitriptyline','aripiprazole','atomoxetine','brexpiprazole',
      'celecoxib','citalopram','clomipramine','clopidogrel',
      'codeine','desipramine','dexlansoprazole','doxepin',
      'efavirenz','escitalopram','flecainide','flurbiprofen',
      'fluvoxamine','hydrocodone','ibuprofen','imipramine',
      'lansoprazole','lornoxicam','meloxicam','methadone',
      'nortriptyline','omeprazole','ondansetron','oxycodone',
      'pantoprazole','paroxetine','pimozide','piroxicam',
      'propafenone','rabeprazole','sertraline','simvastatin',
      'tamoxifen','tenoxicam','tramadol','trimipramine',
      'tropisetron','venlafaxine','voriconazole',
      'atorvastatin','lovastatin','pitavastatin','pravastatin',
      'rosuvastatin','fluvastatin','metoprolol'
    ],
    description: 'No pharmacogenomic-based prescribing changes are recommended. Standard dosing applies.'
  }
};

// Per-drug prescribing information
export const PRESCRIBING_INFO = {
  warfarin: {
    gene: 'VKORC1, CYP2C9, CYP4F2',
    diplotype: 'rs9923231 C/C; CYP2C9 *1/*1; CYP4F2 *1/*1',
    phenotype: 'Warfarin Low Sensitivity; Normal Metabolizer',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'Calculate dose using a validated algorithm; consider clinical factors.',
        recommendation: 'Use pharmacogenomic-based dosing algorithm. Expected dose: 5–7 mg/day based on genotype.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166104949'
      },
      {
        source: 'DPWG',
        summary: 'Genotype-guided dosing reduces time to stable INR.',
        recommendation: 'Recommend dose adjustment using EU-PACT or IWPC algorithm.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166104964'
      }
    ]
  },
  tacrolimus: {
    gene: 'CYP3A5',
    diplotype: '*1/*1',
    phenotype: 'Normal Metabolizer (Extensive)',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'CYP3A5 expressers may need higher initial dose.',
        recommendation: 'Increase starting dose 1.5–2 times recommended. Monitor trough concentrations.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166124619'
      }
    ]
  },
  phenytoin: {
    gene: 'CYP2C9, HLA-B',
    diplotype: 'CYP2C9 *1/*1',
    phenotype: 'Normal Metabolizer',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'HLA-B status should be checked before initiation in at-risk populations.',
        recommendation: 'Standard maintenance dosing for CYP2C9 normal metabolizers. Use with caution pending HLA-B results.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166122806'
      }
    ]
  },
  fosphenytoin: {
    gene: 'CYP2C9, HLA-B',
    diplotype: 'CYP2C9 *1/*1',
    phenotype: 'Normal Metabolizer',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'Fosphenytoin is a prodrug of phenytoin; same PGx considerations apply.',
        recommendation: 'Standard dosing for normal metabolizers. Verify HLA-B status before use.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166122806'
      }
    ]
  },
  fluorouracil: {
    gene: 'DPYD',
    diplotype: 'Reference/Reference',
    phenotype: 'Normal Metabolizer',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'DPYD variants can lead to severe, life-threatening toxicity.',
        recommendation: 'AVOID: Genotyping indicates risk factors. Consider alternative agents or 50% dose reduction with close monitoring.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166122686'
      }
    ]
  },
  capecitabine: {
    gene: 'DPYD',
    diplotype: 'Reference/Reference',
    phenotype: 'Normal Metabolizer',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'Capecitabine is a prodrug of 5-FU; same DPYD considerations apply.',
        recommendation: 'AVOID: Risk of severe fluoropyrimidine toxicity. Use alternative chemotherapy if available.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166122686'
      }
    ]
  },
  codeine: {
    gene: 'CYP2D6',
    diplotype: '*1/*1',
    phenotype: 'Normal Metabolizer',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'Normal metabolizers convert codeine to morphine at expected rates.',
        recommendation: 'Use labeled dosing. Monitor for efficacy. No dose adjustment needed.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166104996'
      }
    ]
  },
  simvastatin: {
    gene: 'SLCO1B1',
    diplotype: '*1/*1',
    phenotype: 'Normal Function',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'SLCO1B1 normal function — standard myopathy risk.',
        recommendation: 'Use standard dosing. Prescribe the desired starting dose.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166105005'
      }
    ]
  },
  clopidogrel: {
    gene: 'CYP2C19',
    diplotype: '*38/*38',
    phenotype: 'Indeterminate',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'CYP2C19 indeterminate phenotype — insufficient evidence to guide dosing.',
        recommendation: 'Use standard dosing. Monitor platelet reactivity if available.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166104948'
      }
    ]
  },
  amitriptyline: {
    gene: 'CYP2D6, CYP2C19',
    diplotype: 'CYP2D6 *1/*1; CYP2C19 *38/*38',
    phenotype: 'Normal Metabolizer; Indeterminate',
    guidelines: [
      {
        source: 'CPIC',
        summary: 'CYP2D6 normal metabolizers process amitriptyline at expected rates.',
        recommendation: 'Initiate standard dose. Titrate based on clinical response and side effects.',
        url: 'https://www.pharmgkb.org/guidelineAnnotation/PA166105006'
      }
    ]
  }
};

// Phenotype predictions: drug → { toxicity, dosage, efficacy, metabolism }
// Values: 'normal', 'increased', 'decreased', 'na'
export const PHENOTYPE_PREDICTIONS = {
  warfarin:     { toxicity: 'normal',    dosage: 'decreased', efficacy: 'normal',    metabolism: 'na' },
  tacrolimus:   { toxicity: 'normal',    dosage: 'increased', efficacy: 'normal',    metabolism: 'increased' },
  codeine:      { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  simvastatin:  { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  clopidogrel:  { toxicity: 'na',        dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  fluorouracil: { toxicity: 'increased', dosage: 'decreased', efficacy: 'normal',    metabolism: 'decreased' },
  capecitabine: { toxicity: 'increased', dosage: 'decreased', efficacy: 'normal',    metabolism: 'decreased' },
  amitriptyline:{ toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  phenytoin:    { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  fosphenytoin: { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  omeprazole:   { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  escitalopram: { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  sertraline:   { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  paroxetine:   { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  tramadol:     { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  ibuprofen:    { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
  metoprolol:   { toxicity: 'normal',    dosage: 'normal',    efficacy: 'normal',    metabolism: 'normal' },
};

// Clinical annotations with evidence levels
export const CLINICAL_ANNOTATIONS = [
  { drug: 'warfarin',      category: 'Dosage',   gene: 'VKORC1',  variant: 'rs9923231', diplotype: 'C/C',    level: '1A', phenotype: 'Lower warfarin dose requirement', pgkbId: 'PA166104949' },
  { drug: 'warfarin',      category: 'Dosage',   gene: 'CYP2C9',  variant: 'rs1799853', diplotype: '*1/*1',  level: '1A', phenotype: 'Standard warfarin metabolism', pgkbId: 'PA166104949' },
  { drug: 'warfarin',      category: 'Dosage',   gene: 'CYP4F2',  variant: 'rs2108622', diplotype: '*1/*1',  level: '2A', phenotype: 'Standard vitamin K metabolism', pgkbId: 'PA166104949' },
  { drug: 'clopidogrel',   category: 'Efficacy', gene: 'CYP2C19', variant: 'rs4244285', diplotype: '*38/*38',level: '1A', phenotype: 'Indeterminate clopidogrel efficacy', pgkbId: 'PA166104948' },
  { drug: 'simvastatin',   category: 'Toxicity', gene: 'SLCO1B1', variant: 'rs4149056', diplotype: '*1/*1',  level: '1A', phenotype: 'Typical myopathy risk', pgkbId: 'PA166105005' },
  { drug: 'codeine',       category: 'Efficacy', gene: 'CYP2D6',  variant: 'rs3892097', diplotype: '*1/*1',  level: '1A', phenotype: 'Normal morphine formation', pgkbId: 'PA166104996' },
  { drug: 'tacrolimus',    category: 'Dosage',   gene: 'CYP3A5',  variant: 'rs776746',  diplotype: '*1/*1',  level: '1A', phenotype: 'May need higher tacrolimus dose', pgkbId: 'PA166124619' },
  { drug: 'fluorouracil',  category: 'Toxicity', gene: 'DPYD',    variant: 'rs3918290', diplotype: 'Ref/Ref',level: '1A', phenotype: 'Risk of severe toxicity', pgkbId: 'PA166122686' },
  { drug: 'capecitabine',  category: 'Toxicity', gene: 'DPYD',    variant: 'rs3918290', diplotype: 'Ref/Ref',level: '1A', phenotype: 'Risk of severe toxicity', pgkbId: 'PA166122686' },
  { drug: 'amitriptyline', category: 'Dosage',   gene: 'CYP2D6',  variant: 'rs3892097', diplotype: '*1/*1',  level: '1A', phenotype: 'Normal amitriptyline metabolism', pgkbId: 'PA166105006' },
  { drug: 'phenytoin',     category: 'Dosage',   gene: 'CYP2C9',  variant: 'rs1799853', diplotype: '*1/*1',  level: '1A', phenotype: 'Standard phenytoin clearance', pgkbId: 'PA166122806' },
  { drug: 'omeprazole',    category: 'Efficacy', gene: 'CYP2C19', variant: 'rs4244285', diplotype: '*38/*38',level: '1A', phenotype: 'Indeterminate PPI metabolism', pgkbId: 'PA166124437' },
  { drug: 'escitalopram',  category: 'Dosage',   gene: 'CYP2C19', variant: 'rs4244285', diplotype: '*38/*38',level: '2A', phenotype: 'Indeterminate escitalopram metabolism', pgkbId: 'PA166127636' },
  { drug: 'tramadol',      category: 'Efficacy', gene: 'CYP2D6',  variant: 'rs3892097', diplotype: '*1/*1',  level: '1B', phenotype: 'Normal tramadol activation', pgkbId: 'PA166228187' },
  { drug: 'ibuprofen',     category: 'Dosage',   gene: 'CYP2C9',  variant: 'rs1799853', diplotype: '*1/*1',  level: '2B', phenotype: 'Standard NSAID metabolism', pgkbId: 'PA166153547' },
  { drug: 'metoprolol',    category: 'Dosage',   gene: 'CYP2D6',  variant: 'rs3892097', diplotype: '*1/*1',  level: '2A', phenotype: 'Normal metoprolol metabolism', pgkbId: 'PA166181498' },
];

// Helper: get risk tier for a drug
export function getDrugRiskTier(drugName) {
  const name = drugName.toLowerCase();
  if (RISK_TIERS.avoid.drugs.includes(name)) return 'avoid';
  if (RISK_TIERS.caution.drugs.includes(name)) return 'caution';
  if (RISK_TIERS.routine.drugs.includes(name)) return 'routine';
  return 'routine'; // default
}

// Helper: get prescribing info for a drug (or a generic fallback)
export function getDrugInfo(drugName) {
  const name = drugName.toLowerCase();
  if (PRESCRIBING_INFO[name]) return PRESCRIBING_INFO[name];
  // Generic fallback
  return {
    gene: 'CYP2D6',
    diplotype: '*1/*1',
    phenotype: 'Normal Metabolizer',
    guidelines: [{
      source: 'CPIC',
      summary: 'No specific pharmacogenomic guidance available for this drug-gene pair.',
      recommendation: 'Use standard prescribing information. No genotype-based dose adjustment recommended.',
      url: 'https://www.pharmgkb.org/'
    }]
  };
}

// Build JSON export
export function buildExportJSON(selectedDrugs) {
  const results = {
    reportDate: new Date().toISOString(),
    sampleId: 'HG00096',
    referenceGenome: 'GRCh38',
    diplotypes: SAMPLE_DIPLOTYPES,
    drugAssessments: {}
  };

  selectedDrugs.forEach(drug => {
    const tier = getDrugRiskTier(drug);
    const info = getDrugInfo(drug);
    const pred = PHENOTYPE_PREDICTIONS[drug.toLowerCase()] || null;
    const annots = CLINICAL_ANNOTATIONS.filter(a => a.drug.toLowerCase() === drug.toLowerCase());

    results.drugAssessments[drug] = {
      riskTier: tier,
      riskLabel: RISK_TIERS[tier].label,
      ...info,
      phenotypePrediction: pred,
      clinicalAnnotations: annots
    };
  });

  return results;
}
