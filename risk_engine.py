"""
PharmaGuard – Component 3: Clinical Phenotyping & Deterministic Risk Stratification Engine

Stateless, synchronous, stdlib-only Python module designed for Appwrite serverless deployment.
Takes a sanitised JSON payload of detected genetic variants, maps them to clinical phenotypes
via local CPIC diplotype tables, and returns strict deterministic risk assessments.

Author:  PharmaGuard / RIFT 2026
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# ──────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────

ALLOWED_GENES: set[str] = {
    "CYP2D6", "CYP2C19", "CYP2C9", "SLCO1B1", "TPMT", "DPYD"
}

DRUG_GENE_MAP: dict[str, str] = {
    "fluorouracil":  "DPYD",
    "capecitabine":  "DPYD",
    "tegafur":       "DPYD",
    "simvastatin":   "SLCO1B1",
    "atorvastatin":  "SLCO1B1",
    "rosuvastatin":  "SLCO1B1",
    "codeine":       "CYP2D6",
    "tramadol":      "CYP2D6",
    "clopidogrel":   "CYP2C19",
    "azathioprine":  "TPMT",
    "mercaptopurine": "TPMT",
    "thioguanine":   "TPMT",
    "warfarin":      "CYP2C9",
    "phenytoin":     "CYP2C9",
}

# Maps CPIC `generesult` values → mandatory output phenotype codes
PHENOTYPE_ABBREV: dict[str, str] = {
    "Normal Metabolizer":              "NM",
    "Normal Function":                 "NM",
    "Increased Function":              "URM",
    "Intermediate Metabolizer":        "IM",
    "Likely Intermediate Metabolizer": "IM",
    "Possible Intermediate Metabolizer": "IM",
    "Decreased Function":              "IM",
    "Possible Decreased Function":     "IM",
    "Poor Metabolizer":                "PM",
    "Poor Function":                   "PM",
    "Rapid Metabolizer":               "RM",
    "Ultrarapid Metabolizer":          "URM",
    "Indeterminate":                   "Unknown",
}

# DPYD star-allele → HGVS alias map (common alleles only)
_DPYD_STAR_TO_HGVS: dict[str, str] = {
    "*2A":  "c.1905+1G>A (*2A)",
    "*3":   "c.1898delC (*3)",
    "*4":   "c.1601G>A (*4)",
    "*5":   "c.1627A>G (*5)",
    "*6":   "c.2194G>A (*6)",
    "*7":   "c.295_298delTCAT (*7)",
    "*8":   "c.703C>T (*8)",
    "*9A":  "c.85T>C (*9A)",
    "*10":  "c.2846A>T (*10)",
    "*11":  "c.1003G>T (*11)",
    "*12":  "c.62G>A (*12)",
    "*13":  "c.1679T>G (*13)",
}


# ──────────────────────────────────────────────────────────
# DIPLOTYPE INDEX BUILDER
# ──────────────────────────────────────────────────────────

def _canonicalise_diplotype(diplotype: str) -> str:
    """Sort the two allele halves of a diplotype string so order doesn't matter."""
    parts = diplotype.split("/")
    if len(parts) == 2:
        return "/".join(sorted(parts))
    return diplotype


def _build_diplotype_index(
    cpic_diplotype_data: Dict[str, List[dict]],
) -> Tuple[Dict[str, Dict[str, dict]], Dict[str, Dict[str, str]]]:
    """
    Build two lookup structures:

    1. diplotype_index – {gene: {canonicalised_diplotype: record, ...}}
    2. dpyd_alias_map  – {canonical_star_diplotype: canonical_hgvs_diplotype}
       so that "*2A/*2A" can be resolved to the HGVS entry.

    Returns (diplotype_index, dpyd_alias_map)
    """
    diplotype_index: Dict[str, Dict[str, dict]] = {}
    dpyd_alias_map: Dict[str, str] = {}

    # Regex to pull "(*NN)" from an HGVS allele string
    _star_re = re.compile(r"\(\*([^)]+)\)")

    for gene, records in cpic_diplotype_data.items():
        gene_map: Dict[str, dict] = {}
        for rec in records:
            raw_dip = rec.get("diplotype", "")
            canon = _canonicalise_diplotype(raw_dip)
            gene_map[canon] = rec

            # Build DPYD alias entries
            if gene == "DPYD":
                allele_halves = raw_dip.split("/")
                if len(allele_halves) == 2:
                    stars = []
                    for half in allele_halves:
                        m = _star_re.search(half)
                        if m:
                            stars.append(f"*{m.group(1)}")
                    if len(stars) == 2:
                        star_canon = _canonicalise_diplotype(f"{stars[0]}/{stars[1]}")
                        hgvs_canon = canon
                        # Only keep first seen (i.e. don't overwrite)
                        if star_canon not in dpyd_alias_map:
                            dpyd_alias_map[star_canon] = hgvs_canon

        diplotype_index[gene] = gene_map

    return diplotype_index, dpyd_alias_map


# ──────────────────────────────────────────────────────────
# PHENOTYPE RESOLVER
# ──────────────────────────────────────────────────────────

def _resolve_phenotype(
    gene: str,
    diplotype: str,
    status: str,
    diplotype_index: Dict[str, Dict[str, dict]],
    dpyd_alias_map: Dict[str, str],
) -> dict:
    """
    Look up a diplotype in the CPIC tables and return:
        {
          "phenotype":   "PM" | "IM" | "NM" | "RM" | "URM" | "Unknown",
          "generesult":  raw CPIC string or "Unknown",
          "lookupkey":   dict or None,
          "matched_diplotype": str or None,
        }
    """
    unknown = {
        "phenotype": "Unknown",
        "generesult": "Unknown",
        "lookupkey": None,
        "matched_diplotype": None,
    }

    # Rule 2: uncertain status → immediate Unknown
    if status == "uncertain":
        return unknown

    gene_map = diplotype_index.get(gene)
    if not gene_map:
        return unknown

    canon = _canonicalise_diplotype(diplotype)
    record = gene_map.get(canon)

    # If not found and DPYD, try star-allele alias
    if record is None and gene == "DPYD":
        hgvs_canon = dpyd_alias_map.get(canon)
        if hgvs_canon:
            record = gene_map.get(hgvs_canon)

    if record is None:
        return unknown

    generesult = record.get("generesult", "Indeterminate")
    phenotype = PHENOTYPE_ABBREV.get(generesult, "Unknown")
    lookupkey = record.get("lookupkey")

    return {
        "phenotype": phenotype,
        "generesult": generesult,
        "lookupkey": lookupkey,
        "matched_diplotype": record.get("diplotype"),
    }


# ──────────────────────────────────────────────────────────
# RECOMMENDATION LOOKUP
# ──────────────────────────────────────────────────────────

def _parse_score(val: str) -> Optional[float]:
    """Try to parse a numeric activity-score string; return None on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _find_recommendation(
    drug: str,
    lookupkey: Optional[dict],
    cpic_recs: List[dict],
) -> Optional[dict]:
    """
    Find the best CPIC recommendation for a drug given a diplotype's lookupkey.

    Handles:
      - Exact-match single-gene lookupkeys  (e.g. {"DPYD": "0.0"})
      - Exact-match phenotype-string keys    (e.g. {"SLCO1B1": "Poor Function"})
      - "≥" threshold keys for CYP2D6        (e.g. {"CYP2D6": "≥3.75"})
    """
    if lookupkey is None:
        return None

    drug_lower = drug.lower()

    # Pre-filter to the relevant drug + general population
    candidates = [
        r for r in cpic_recs
        if r.get("drugname", "").lower() == drug_lower
        and r.get("population", "").strip().lower() == "general"
    ]

    if not candidates:
        return None

    # Determine the gene and value from the incoming lookupkey
    gene_key = list(lookupkey.keys())[0]
    lookup_val = lookupkey[gene_key]
    lookup_score = _parse_score(lookup_val)

    # Pass 1: exact match
    for rec in candidates:
        rec_lk = rec.get("lookupkey", {})
        if rec_lk == lookupkey:
            return rec

    # Pass 2: numeric threshold match ("≥X.X" keys) – only if lookup_val is numeric
    if lookup_score is not None:
        best_rec = None
        best_threshold = None

        for rec in candidates:
            rec_lk = rec.get("lookupkey", {})
            rec_val = rec_lk.get(gene_key, "")
            if isinstance(rec_val, str) and rec_val.startswith("≥"):
                try:
                    threshold = float(rec_val[1:])
                except ValueError:
                    continue
                if lookup_score >= threshold:
                    # Pick the highest threshold that still matches (most specific)
                    if best_threshold is None or threshold > best_threshold:
                        best_threshold = threshold
                        best_rec = rec

        if best_rec is not None:
            return best_rec

    return None


# ──────────────────────────────────────────────────────────
# RISK CLASSIFICATION
# ──────────────────────────────────────────────────────────

def _classify_risk(
    drug: str,
    phenotype: str,
    recommendation: Optional[dict],
) -> dict:
    """
    Derive risk_label, severity and confidence_score from a CPIC recommendation.

    Returns {"risk_label": str, "severity": str, "confidence_score": float}
    """
    # Default / Unknown path
    if recommendation is None or phenotype == "Unknown":
        return {
            "risk_label": "Unknown",
            "severity": "low/moderate",
            "confidence_score": 0.0,
        }

    rec_text: str = recommendation.get("drugrecommendation", "").lower()
    classification: str = recommendation.get("classification", "")
    rec_phenotype: str = phenotype  # abbreviated

    # ── risk_label derivation ──
    risk_label = "Unknown"

    if "avoid" in rec_text:
        # Distinguish Toxic vs Ineffective for codeine
        if drug.lower() == "codeine" and rec_phenotype == "PM":
            risk_label = "Ineffective"
        else:
            risk_label = "Toxic"
    elif "reduce" in rec_text or "limit dose" in rec_text:
        risk_label = "Adjust Dosage"
    elif "alternative statin" in rec_text or "prescribe an alternative" in rec_text:
        # SLCO1B1 recommendations say "prescribe an alternative statin" –
        # this is effectively "avoid simvastatin"
        risk_label = "Toxic"
    elif "label recommended" in rec_text or "desired starting dose" in rec_text:
        risk_label = "Safe"
    elif classification == "No Recommendation":
        risk_label = "Unknown"

    # ── severity derivation ──
    if risk_label == "Safe":
        severity = "none"
    elif risk_label == "Adjust Dosage":
        severity = "low/moderate"
    elif risk_label in ("Toxic", "Ineffective"):
        severity = "critical" if classification == "Strong" else "high"
    else:
        severity = "low/moderate"

    # ── confidence_score derivation ──
    if classification == "Strong":
        confidence = 1.0
    elif classification == "Moderate":
        confidence = 0.75
    else:
        confidence = 0.0

    return {
        "risk_label": risk_label,
        "severity": severity,
        "confidence_score": confidence,
    }


# ──────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────

def generate_risk_profiles(
    input_json: Union[str, dict],
    cpic_diplotype_data: Dict[str, List[dict]],
    cpic_recommendation_data: List[dict],
) -> dict:
    """
    Main entry point for the risk stratification engine.

    Parameters
    ----------
    input_json : str | dict
        The sanitised payload from the VCF parser (see output.json schema).
    cpic_diplotype_data : dict[str, list[dict]]
        Keyed by gene symbol, e.g. {"CYP2D6": [...], "DPYD": [...]}.
        Each value is the parsed contents of the corresponding diplotype_*.json.
    cpic_recommendation_data : list[dict]
        Parsed contents of cpic_recommendations.json.

    Returns
    -------
    dict  with keys:
        - request_id        : echoed from input
        - timestamp         : ISO-8601 UTC string
        - engine_version    : semver tag
        - results           : list of per-drug result dicts
    """
    # ── Parse input ──
    if isinstance(input_json, str):
        try:
            payload: dict = json.loads(input_json)
        except (json.JSONDecodeError, TypeError):
            return _error_response("Invalid JSON input")
    else:
        payload = input_json

    request_id: str = payload.get("request_id", "unknown")
    target_drugs: List[str] = payload.get("target_drugs", [])
    resolved_profiles: List[dict] = payload.get("resolved_profiles", [])

    # ── Build lookup structures ──
    diplotype_index, dpyd_alias_map = _build_diplotype_index(cpic_diplotype_data)

    # ── Filter profiles to allowed genes ──
    gene_profiles: Dict[str, dict] = {}
    for profile in resolved_profiles:
        gene = profile.get("gene", "")
        if gene in ALLOWED_GENES:
            gene_profiles[gene] = profile

    # ── Process each target drug ──
    results: List[dict] = []
    for drug in target_drugs:
        try:
            result = _process_drug(
                drug, gene_profiles, diplotype_index, dpyd_alias_map,
                cpic_recommendation_data,
            )
        except Exception:
            # Absolute safety net – never crash the Appwrite function
            result = _unknown_drug_result(drug)
        results.append(result)

    from datetime import datetime, timezone
    return {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_version": "1.0.0",
        "results": results,
    }


# ──────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────

def _process_drug(
    drug: str,
    gene_profiles: Dict[str, dict],
    diplotype_index: Dict[str, Dict[str, dict]],
    dpyd_alias_map: Dict[str, str],
    cpic_recs: List[dict],
) -> dict:
    """Build the full output dict for a single drug."""

    primary_gene = DRUG_GENE_MAP.get(drug.lower())
    if primary_gene is None:
        return _unknown_drug_result(drug)

    profile = gene_profiles.get(primary_gene)
    if profile is None:
        return _unknown_drug_result(drug, primary_gene=primary_gene)

    diplotype_raw = profile.get("diplotype", "")
    status = profile.get("status", "resolved")
    rsids = profile.get("contributing_rsids", [])

    # Step 1: Phenotype resolution
    pheno = _resolve_phenotype(
        primary_gene, diplotype_raw, status,
        diplotype_index, dpyd_alias_map,
    )

    # Step 2: Recommendation lookup
    recommendation = _find_recommendation(drug, pheno["lookupkey"], cpic_recs)

    # Step 3: Risk classification
    risk = _classify_risk(drug, pheno["phenotype"], recommendation)

    return {
        "drug": drug.lower(),
        "risk_assessment": {
            "risk_label": risk["risk_label"],
            "confidence_score": risk["confidence_score"],
            "severity": risk["severity"],
        },
        "pharmacogenomic_profile": {
            "primary_gene": primary_gene,
            "diplotype": diplotype_raw,
            "phenotype": pheno["phenotype"],
            "detected_variants": [{"rsid": r} for r in rsids],
        },
        "cpic_metadata": _extract_cpic_metadata(recommendation),
    }


def _extract_cpic_metadata(recommendation: Optional[dict]) -> dict:
    """Pull useful CPIC context fields for the LLM explanation generator."""
    if recommendation is None:
        return {
            "guideline_name": None,
            "guideline_url": None,
            "drug_recommendation": None,
            "classification": None,
            "implications": None,
        }
    return {
        "guideline_name": recommendation.get("guidelinename"),
        "guideline_url": recommendation.get("guidelineurl"),
        "drug_recommendation": recommendation.get("drugrecommendation"),
        "classification": recommendation.get("classification"),
        "implications": recommendation.get("implications"),
    }


def _unknown_drug_result(drug: str, primary_gene: Optional[str] = None) -> dict:
    """Produce a safe Unknown result for a drug that couldn't be resolved."""
    return {
        "drug": drug.lower(),
        "risk_assessment": {
            "risk_label": "Unknown",
            "confidence_score": 0.0,
            "severity": "low/moderate",
        },
        "pharmacogenomic_profile": {
            "primary_gene": primary_gene or DRUG_GENE_MAP.get(drug.lower(), "Unknown"),
            "diplotype": "Unknown",
            "phenotype": "Unknown",
            "detected_variants": [],
        },
        "cpic_metadata": _extract_cpic_metadata(None),
    }


def _error_response(message: str) -> dict:
    from datetime import datetime, timezone
    return {
        "request_id": "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_version": "1.0.0",
        "error": message,
        "results": [],
    }


# ──────────────────────────────────────────────────────────
# CLI TEST HARNESS
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import sys

    BASE = os.path.dirname(os.path.abspath(__file__))

    def _load(fname: str) -> Any:
        path = os.path.join(BASE, fname)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Load all diplotype tables
    GENE_FILES = {
        "CYP2D6":  "diplotype_CYP2D6.json",
        "CYP2C19": "diplotype_CYP2C19.json",
        "CYP2C9":  "diplotype_CYP2C9.json",
        "SLCO1B1": "diplotype_SLCO1B1.json",
        "TPMT":    "diplotype_TPMT.json",
        "DPYD":    "diplotype_DPYD.json",
    }

    print("Loading CPIC diplotype tables …")
    cpic_diplotypes: Dict[str, List[dict]] = {}
    for gene, fname in GENE_FILES.items():
        cpic_diplotypes[gene] = _load(fname)
        print(f"  {gene}: {len(cpic_diplotypes[gene]):,} entries")

    print("Loading CPIC recommendations …")
    cpic_recs = _load("cpic_recommendations.json")
    print(f"  {len(cpic_recs):,} recommendation entries")

    print("Loading input payload (output.json) …")
    input_payload = _load("output.json")

    print("\n" + "=" * 60)
    print("  RUNNING RISK STRATIFICATION ENGINE")
    print("=" * 60 + "\n")

    result = generate_risk_profiles(input_payload, cpic_diplotypes, cpic_recs)
    print(json.dumps(result, indent=2))

    # Quick assertion checks for the edge-case payload
    print("\n" + "=" * 60)
    print("  VALIDATION CHECKS")
    print("=" * 60)

    for r in result.get("results", []):
        drug = r["drug"]
        risk = r["risk_assessment"]["risk_label"]
        pheno = r["pharmacogenomic_profile"]["phenotype"]
        sev = r["risk_assessment"]["severity"]
        conf = r["risk_assessment"]["confidence_score"]

        if drug == "fluorouracil":
            assert pheno == "PM", f"DPYD *2A/*2A should be PM, got {pheno}"
            assert risk == "Toxic", f"fluorouracil+PM should be Toxic, got {risk}"
            assert sev == "critical", f"severity should be critical, got {sev}"
            assert conf == 1.0, f"confidence should be 1.0, got {conf}"
            print(f"  ✓ fluorouracil: {pheno} → {risk} ({sev}, conf={conf})")

        elif drug == "simvastatin":
            assert pheno == "PM", f"SLCO1B1 *5/*15 should be PM, got {pheno}"
            assert risk == "Toxic", f"simvastatin+PM should be Toxic, got {risk}"
            assert sev == "critical", f"severity should be critical, got {sev}"
            print(f"  ✓ simvastatin:  {pheno} → {risk} ({sev}, conf={conf})")

        elif drug == "codeine":
            assert pheno == "Unknown", f"CYP2D6 *4+*41/*10 should be Unknown, got {pheno}"
            assert risk == "Unknown", f"codeine+Unknown should be Unknown, got {risk}"
            assert conf == 0.0, f"confidence should be 0.0, got {conf}"
            print(f"  ✓ codeine:      {pheno} → {risk} ({sev}, conf={conf})")

    print("\n  All edge-case assertions passed.\n")
