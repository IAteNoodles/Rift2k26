"""
Parses PharmCAT phenotype.json + report.json + match.json into a concise summary,
and builds the intermediate payload required by the risk stratification engine.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ── Genes the risk engine cares about ───────────────────────
_RISK_ENGINE_GENES: set[str] = {
    "CYP2D6", "CYP2C19", "CYP2C9", "SLCO1B1", "TPMT", "DPYD",
}


# ─────────────────────────────────────────────────────────────
# 1.  PARSE PHENOTYPE + REPORT (existing, cleaned up)
# ─────────────────────────────────────────────────────────────

def parse_results(
    output_dir: str,
    base_name: str,
    *,
    drug_filter: list[str] | None = None,
) -> dict[str, Any]:
    """
    Read PharmCAT output files and return a concise JSON-friendly summary.

    Parameters
    ----------
    output_dir : str
        Directory containing PharmCAT output files.
    base_name : str
        The base filename (without extension) that PharmCAT used.
    drug_filter : list[str] | None
        If provided, only return recommendations for these drugs (lowercase).

    Returns
    -------
    dict – concise summary with genes, recommendations, and metadata.
    """
    out = Path(output_dir)

    pheno_path = out / f"{base_name}.phenotype.json"
    report_path = out / f"{base_name}.report.json"

    # ── Gene calls ──────────────────────────────────────────
    genes_summary: list[dict] = []
    if pheno_path.exists():
        pheno = json.loads(pheno_path.read_text())

        for gene_name, gene_data in sorted(pheno.get("geneReports", {}).items()):
            for d in gene_data.get("sourceDiplotypes", []):
                label = d.get("label", "")
                if not label or label == "Unknown/Unknown":
                    continue

                phenotypes = d.get("phenotypes", [])
                phenotype = phenotypes[0] if phenotypes else None
                if phenotype in ("No Result", None):
                    continue

                allele1 = (d.get("allele1") or {}).get("name", "")
                allele2 = (d.get("allele2") or {}).get("name", "")
                activity = d.get("activityScore")

                genes_summary.append({
                    "gene": gene_name,
                    "diplotype": label,
                    "allele1": allele1,
                    "allele2": allele2,
                    "phenotype": phenotype,
                    "activityScore": activity,
                    "lookupKey": d.get("lookupKey", []),
                })

    # ── Drug recommendations (from report.json) ────────────
    recommendations: list[dict] = []
    all_drugs: list[str] = []

    if report_path.exists():
        report = json.loads(report_path.read_text())

        # PharmCAT report.json may store drugs in different structures
        # depending on version.  Handle both "drugs" (dict-of-dicts)
        # and "reportDrugs" (list-of-dicts).
        drugs_container = report.get("drugs", {})
        if isinstance(drugs_container, dict):
            _parse_drugs_dict(drugs_container, drug_filter, recommendations, all_drugs)
        elif isinstance(drugs_container, list):
            _parse_drugs_list(drugs_container, drug_filter, recommendations, all_drugs)

    # ── Called vs uncalled genes ─────────────────────────────
    called_genes = [g["gene"] for g in genes_summary]
    uncalled_genes: list[str] = []
    if pheno_path.exists():
        pheno = json.loads(pheno_path.read_text())
        for gene_name, gene_data in sorted(pheno.get("geneReports", {}).items()):
            diplotypes = gene_data.get("sourceDiplotypes", [])
            if not diplotypes or diplotypes[0].get("label", "") == "Unknown/Unknown":
                uncalled_genes.append(gene_name)

    # ── Metadata ────────────────────────────────────────────
    metadata = {}
    if report_path.exists():
        report = json.loads(report_path.read_text())
        metadata = {
            "pharmcatVersion": report.get("pharmcatVersion"),
            "dataVersion": report.get("dataVersion"),
            "timestamp": report.get("timestamp"),
            "title": report.get("title"),
        }

    return {
        "metadata": metadata,
        "geneCalls": genes_summary,
        "calledGeneCount": len(called_genes),
        "uncalledGenes": uncalled_genes,
        "recommendations": recommendations,
        "totalDrugsEvaluated": len(all_drugs),
        "actionableRecommendationCount": sum(
            1 for r in recommendations if r.get("classification") not in ("", None, "No Recommendation")
        ),
    }


# ── helpers for drug parsing ────────────────────────────────

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_rec_text(text: str, max_len: int = 500) -> str:
    cleaned = _HTML_TAG_RE.sub("", text).strip()
    return cleaned[:max_len] + "…" if len(cleaned) > max_len else cleaned


def _parse_drugs_dict(
    drugs_container: dict,
    drug_filter: list[str] | None,
    recommendations: list[dict],
    all_drugs: list[str],
) -> None:
    """Parse 'drugs' when it's the nested dict-of-dicts format."""
    for source_name, drugs_map in drugs_container.items():
        if not isinstance(drugs_map, dict):
            continue
        for drug_key, drug_data in drugs_map.items():
            _extract_drug(drug_data, drug_key, source_name, drug_filter, recommendations, all_drugs)


def _parse_drugs_list(
    drugs_container: list,
    drug_filter: list[str] | None,
    recommendations: list[dict],
    all_drugs: list[str],
) -> None:
    """Parse 'drugs' when it's the list format (newer PharmCAT)."""
    for drug_entry in drugs_container:
        drug_key = drug_entry.get("name", drug_entry.get("drugName", ""))
        source_name = drug_entry.get("source", "")
        _extract_drug(drug_entry, drug_key, source_name, drug_filter, recommendations, all_drugs)


def _extract_drug(
    drug_data: dict,
    drug_key: str,
    source_name: str,
    drug_filter: list[str] | None,
    recommendations: list[dict],
    all_drugs: list[str],
) -> None:
    drug_name = drug_data.get("name", drug_key)
    if drug_filter is not None and drug_name.lower() not in drug_filter:
        return
    if drug_name not in all_drugs:
        all_drugs.append(drug_name)

    for gl in drug_data.get("guidelines", []):
        gl_source = gl.get("source", source_name)
        for ann in gl.get("annotations", []):
            classification = ann.get("classification", "")
            if not classification:
                continue

            drug_rec_clean = _clean_rec_text(ann.get("drugRecommendation", ""))
            implications = ann.get("implications", [])
            population = ann.get("population", "general")

            genotype_info = []
            for geno_group in ann.get("genotypes", []):
                for dip in geno_group.get("diplotypes", []):
                    genotype_info.append({
                        "gene": dip.get("gene", ""),
                        "diplotype": dip.get("label", ""),
                        "phenotype": dip.get("phenotypes", [None])[0],
                    })

            recommendations.append({
                "drug": drug_name,
                "source": gl_source,
                "classification": classification,
                "recommendation": drug_rec_clean,
                "implications": implications,
                "activityScores": ann.get("activityScore", {}),
                "population": population,
                "genotypes": genotype_info[:3],
            })


# ─────────────────────────────────────────────────────────────
# 2.  EXTRACT PATIENT ID
# ─────────────────────────────────────────────────────────────

def extract_patient_id(output_dir: str, base_name: str) -> str:
    """
    Extract the patient/sample ID from PharmCAT output files.
    Tries phenotype.json first (matcherMetadata.sampleId), then match.json.
    Falls back to base_name.
    """
    out = Path(output_dir)

    # Try phenotype.json
    pheno_path = out / f"{base_name}.phenotype.json"
    if pheno_path.exists():
        pheno = json.loads(pheno_path.read_text())
        sample_id = pheno.get("matcherMetadata", {}).get("sampleId")
        if sample_id:
            return sample_id

    # Try match.json
    match_path = out / f"{base_name}.match.json"
    if match_path.exists():
        match_data = json.loads(match_path.read_text())
        sample_id = match_data.get("metadata", {}).get("sampleId")
        if sample_id:
            return sample_id

    return base_name


# ─────────────────────────────────────────────────────────────
# 3.  BUILD RISK ENGINE INPUT (PharmCAT → risk_engine bridge)
# ─────────────────────────────────────────────────────────────

def build_risk_engine_input(
    output_dir: str,
    base_name: str,
    target_drugs: list[str],
    request_id: str = "unknown",
) -> dict:
    """
    Read PharmCAT phenotype.json and match.json, and produce the intermediate
    JSON payload that risk_engine.generate_risk_profiles() expects.

    Parameters
    ----------
    output_dir : str
        Directory containing PharmCAT output files.
    base_name : str
        Base filename (without extension) PharmCAT used for outputs.
    target_drugs : list[str]
        List of drug names the user is querying.
    request_id : str
        Unique request / job identifier.

    Returns
    -------
    dict  – in the format:
        {
            "request_id": "...",
            "target_drugs": [...],
            "resolved_profiles": [
                {"gene": "CYP2C9", "diplotype": "*1/*1",
                 "contributing_rsids": ["rs..."], "status": "resolved"},
                ...
            ]
        }
    """
    out = Path(output_dir)

    # ── 1. Parse phenotype.json for gene calls ──────────────
    pheno_path = out / f"{base_name}.phenotype.json"
    gene_diplotypes: dict[str, dict] = {}  # gene → best diplotype info

    if pheno_path.exists():
        pheno = json.loads(pheno_path.read_text())

        for gene_name, gene_data in pheno.get("geneReports", {}).items():
            if gene_name not in _RISK_ENGINE_GENES:
                continue

            # Pick the first sourceDiplotype with a valid label
            for d in gene_data.get("sourceDiplotypes", []):
                label = d.get("label", "")
                if not label or label == "Unknown/Unknown":
                    continue

                phenotypes = d.get("phenotypes", [])
                phenotype = phenotypes[0] if phenotypes else "No Result"

                # Determine status
                status = "resolved"
                if phenotype == "No Result":
                    status = "uncertain"

                gene_diplotypes[gene_name] = {
                    "gene": gene_name,
                    "diplotype": label,
                    "status": status,
                    "contributing_rsids": [],  # populated from match.json below
                }
                break  # take the first valid diplotype only

    # ── 2. Parse match.json for variant rsids ───────────────
    match_path = out / f"{base_name}.match.json"
    if match_path.exists():
        match_data = json.loads(match_path.read_text())

        for result in match_data.get("results", []):
            gene = result.get("gene", "")
            if gene not in gene_diplotypes:
                continue

            rsids = set()
            for var in result.get("variants", []):
                rsid = var.get("rsid")
                if rsid:
                    rsids.add(rsid)
            # Also check variantsOfInterest
            for var in result.get("variantsOfInterest", []):
                rsid = var.get("rsid")
                if rsid:
                    rsids.add(rsid)

            if rsids:
                gene_diplotypes[gene]["contributing_rsids"] = sorted(rsids)

    # ── 3. Assemble the payload ─────────────────────────────
    resolved_profiles = list(gene_diplotypes.values())

    return {
        "request_id": request_id,
        "target_drugs": target_drugs,
        "resolved_profiles": resolved_profiles,
    }


# ─────────────────────────────────────────────────────────────
# 4.  EXTRACT GENOME DATA (concise per-gene summary)
# ─────────────────────────────────────────────────────────────

def extract_genome_data(output_dir: str, base_name: str) -> list[dict]:
    """
    Extract a concise genome summary from PharmCAT phenotype.json.
    Returns only genes relevant to the risk engine.

    Returns
    -------
    list[dict] – each entry:
        {"gene": "CYP2C9", "diplotype": "*1/*1",
         "phenotype": "Normal Metabolizer", "activity_score": "2.0",
         "allele1": "*1", "allele2": "*1"}
    """
    out = Path(output_dir)
    pheno_path = out / f"{base_name}.phenotype.json"
    if not pheno_path.exists():
        return []

    pheno = json.loads(pheno_path.read_text())
    result: list[dict] = []

    for gene_name, gene_data in sorted(pheno.get("geneReports", {}).items()):
        if gene_name not in _RISK_ENGINE_GENES:
            continue

        for d in gene_data.get("sourceDiplotypes", []):
            label = d.get("label", "")
            if not label or label == "Unknown/Unknown":
                continue

            phenotypes = d.get("phenotypes", [])
            phenotype = phenotypes[0] if phenotypes else "No Result"
            if phenotype == "No Result":
                continue

            allele1 = (d.get("allele1") or {}).get("name", "")
            allele2 = (d.get("allele2") or {}).get("name", "")
            activity = d.get("activityScore")

            result.append({
                "gene": gene_name,
                "diplotype": label,
                "phenotype": phenotype,
                "activity_score": activity,
                "allele1": allele1,
                "allele2": allele2,
            })
            break  # one per gene

    return result
