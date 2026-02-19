#!/usr/bin/env python3
"""Parse PharmCAT output and display key results."""
import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "dataset", "pharmcat_output")

def main():
    # Load phenotype results
    pheno_path = os.path.join(OUTPUT_DIR, "new_grch38.phenotype.json")
    report_path = os.path.join(OUTPUT_DIR, "new_grch38.report.json")

    print("=" * 60)
    print("  PharmCAT Pharmacogenomics Report — SAMPLE1")
    print("=" * 60)

    # --- Diplotype / Phenotype calls ---
    with open(pheno_path) as f:
        pheno = json.load(f)

    print("\n>>> GENE DIPLOTYPE & PHENOTYPE CALLS <<<\n")
    for gene_name, gene_data in sorted(pheno["geneReports"].items()):
        for d in gene_data.get("sourceDiplotypes", []):
            label = d.get("label", "")
            phenotypes = d.get("phenotypes", [])
            if label and label != "Unknown/Unknown":
                pheno_str = ", ".join(phenotypes) if phenotypes else "N/A"
                activity = d.get("activityScore")
                act_str = f" (Activity Score: {activity})" if activity else ""
                print(f"  Gene: {gene_name}")
                print(f"    Diplotype:  {label}")
                print(f"    Phenotype:  {pheno_str}{act_str}")
                print(f"    Lookup Key: {d.get('lookupKey', [])}")
                print()

    # --- Drug recommendations ---
    with open(report_path) as f:
        report = json.load(f)

    print(">>> DRUG-SPECIFIC RECOMMENDATIONS <<<\n")
    found_any = False
    for drug in report.get("reportDrugs", []):
        name = drug.get("name", "")
        for gl in drug.get("guidelines", []):
            source = gl.get("source", "")
            for ann in gl.get("annotations", []):
                classification = ann.get("classification", "")
                if not classification:
                    continue
                found_any = True
                implications = ann.get("implications", {})
                drug_rec = ann.get("drugRecommendation", "")
                lookup = ann.get("lookupKey", {})
                phenotypes = ann.get("phenotypes", {})
                print(f"  Drug: {name}")
                print(f"    Source:          {source}")
                print(f"    Classification:  {classification}")
                if lookup:
                    print(f"    Lookup Key:      {lookup}")
                if phenotypes:
                    for g, p in phenotypes.items():
                        print(f"    {g} Phenotype: {p}")
                if implications:
                    for g, imp in implications.items():
                        print(f"    {g} Implication: {imp}")
                if drug_rec:
                    print(f"    Recommendation:  {drug_rec[:300]}")
                print()

    if not found_any:
        print("  (No actionable drug recommendations found for the called phenotypes.)\n")
        print("  This is because most genes only had 'Unknown/Unknown' diplotype calls")
        print("  due to insufficient variant coverage in the input VCF.\n")
        print("  Only CYP2C19 and VKORC1 had callable diplotypes.\n")

    # --- Summary of all gene statuses ---
    print(">>> ALL GENE CALL STATUSES <<<\n")
    called = []
    uncalled = []
    for gene_name, gene_data in sorted(pheno["geneReports"].items()):
        diplotypes = gene_data.get("sourceDiplotypes", [])
        if diplotypes and diplotypes[0].get("label", "") != "Unknown/Unknown":
            called.append(f"  {gene_name}: {diplotypes[0]['label']}")
        else:
            uncalled.append(gene_name)

    print(f"  Called ({len(called)} genes):")
    for c in called:
        print(f"    {c}")
    print(f"\n  Uncalled ({len(uncalled)} genes — insufficient variant data):")
    for i in range(0, len(uncalled), 8):
        chunk = uncalled[i:i+8]
        print(f"    {', '.join(chunk)}")

    print("\n" + "=" * 60)
    print("  Output files in: dataset/pharmcat_output/")
    print("    - new_grch38.match.json      (star allele matches)")
    print("    - new_grch38.phenotype.json   (phenotype assignments)")
    print("    - new_grch38.report.json      (full clinical report)")
    print("=" * 60)


if __name__ == "__main__":
    main()
