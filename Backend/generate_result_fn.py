"""
Appwrite Function – generate_result
Production-ready version (optimized for Appwrite containers)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

# ─────────────────────────────────────────────────────────────
# THIRD PARTY
# ─────────────────────────────────────────────────────────────
from pydantic import BaseModel, Field
from groq import Groq
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# GLOBALS (persist across Appwrite executions)
# ─────────────────────────────────────────────────────────────
_GROQ_MODEL = "llama-3.3-70b-versatile"
_groq_client: Optional[Groq] = None

# GLOBAL CACHE (container lifetime cache)
_URL_CACHE: dict[str, list] = {}

# ─────────────────────────────────────────────────────────────
# GROQ INIT (RUN ONCE PER CONTAINER)
# ─────────────────────────────────────────────────────────────
def _init_groq():
    global _groq_client

    key = os.getenv("GROQ_API_KEY")

    if not key:
        log.warning("GROQ_API_KEY missing — running in fallback mode")
        return

    _groq_client = Groq(api_key=key)
    log.info("Groq client initialized")


_init_groq()  # ← runs once at cold start


# ══════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════

class DetectedVariant(BaseModel):
    rsid: str


class RiskAssessment(BaseModel):
    risk_label: str
    confidence_score: float
    severity: str


class PharmacogenomicProfile(BaseModel):
    primary_gene: str
    diplotype: str
    phenotype: str
    detected_variants: list[DetectedVariant]


class CpicMetadata(BaseModel):
    guideline_name: Optional[str] = None
    guideline_url: Optional[str] = None
    drug_recommendation: Optional[str] = None
    classification: Optional[str] = None
    implications: Optional[dict[str, str]] = None


class DrugResult(BaseModel):
    drug: str
    risk_assessment: RiskAssessment
    pharmacogenomic_profile: PharmacogenomicProfile
    cpic_metadata: CpicMetadata


class QualityMetrics(BaseModel):
    model_config = {"extra": "allow"}
    vcf_parsing_success: bool = True


class ClinicalRecommendation(BaseModel):
    guideline_name: Optional[str] = None
    drug_recommendation: Optional[str] = None
    classification: Optional[str] = None
    implications: Optional[dict[str, str]] = None
    cpic_update: Optional[str] = None
    source: str = "none"


class DrugResultOutput(BaseModel):
    drug: str
    risk_assessment: RiskAssessment
    pharmacogenomic_profile: PharmacogenomicProfile
    clinical_recommendation: ClinicalRecommendation


class LLMGeneratedExplanation(BaseModel):
    summary: str
    per_drug: dict[str, str]


class PerDrugLLMExplanation(BaseModel):
    summary: str = Field(..., description="LLM-generated clinical explanation for this drug")


class PerDrugOutput(BaseModel):
    """Flat per-drug result record — returned as a list (one entry per drug)."""
    patient_id:                str
    drug:                      str
    timestamp:                 str
    risk_assessment:           RiskAssessment
    pharmacogenomic_profile:   PharmacogenomicProfile
    clinical_recommendation:   ClinicalRecommendation
    llm_generated_explanation: PerDrugLLMExplanation
    quality_metrics:           QualityMetrics


class GenerateResultRequest(BaseModel):
    patient_id: str
    engine_version: Optional[str] = None
    quality_metrics: QualityMetrics = Field(default_factory=QualityMetrics)
    results: list[DrugResult]


class GenerateResultOutput(BaseModel):
    patient_id: str
    timestamp: str
    engine_version: Optional[str]
    quality_metrics: QualityMetrics
    results: list[DrugResultOutput]
    llm_generated_explanation: LLMGeneratedExplanation


# ══════════════════════════════════════════════════════════════
# CPIC SCRAPER (FAST + SAFE)
# ══════════════════════════════════════════════════════════════

_HEADERS = {"User-Agent": "PGxBot/1.0"}

def scrape_cpic_updates(url: str):

    # GLOBAL CACHE HIT
    if url in _URL_CACHE:
        return _URL_CACHE[url]

    resp = requests.get(url, headers=_HEADERS, timeout=8)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    marker = soup.find(string=re.compile("updates since publication", re.I))
    if not marker:
        _URL_CACHE[url] = []
        return []

    texts = []
    for p in marker.find_all_next("p", limit=4):
        texts.append(p.get_text(" ", strip=True))

    result = [{"text": "\n\n".join(texts)}] if texts else []
    _URL_CACHE[url] = result
    return result


# ══════════════════════════════════════════════════════════════
# LLM HELPERS
# ══════════════════════════════════════════════════════════════

def _call_llm(system, prompt, fallback):

    if _groq_client is None:
        return fallback

    try:
        r = _groq_client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=250,
        )
        return r.choices[0].message.content.strip()

    except Exception as e:
        log.warning(f"LLM failed: {e}")
        return fallback


def _llm_explain(drug, text):
    system = (
        "You are a clinical pharmacogenomics expert. "
        "Write a concise clinical summary of the CPIC guideline update provided. "
        "Open with one sentence stating what changed and why it matters clinically. "
        "Follow with bullet points only for distinct, actionable clinical items. "
        "Use plain prose otherwise. Do not add preamble or closing remarks. Under 180 words."
    )
    return _call_llm(system, f"Drug: {drug}\n\nCPIC guideline update:\n{text}", text)


def _llm_fallback(drug, reason, context):
    """
    Used when scraping fails or no URL is present.
    Generates a clinical explanation from pharmacogenomics knowledge + payload context.
    """
    issue_notes = {
        "none":         "No CPIC guideline URL is available for this drug.",
        "no_updates":   "No 'Updates since publication' section was found on the CPIC guideline page.",
        "scrape_error": "The CPIC guideline page could not be fetched.",
    }
    note = issue_notes.get(reason, "Guideline data unavailable.")
    system = (
        "You are a clinical pharmacogenomics expert. "
        "A CPIC guideline lookup encountered an issue described below. "
        "First, acknowledge the issue in one sentence. "
        "Then, drawing on your full pharmacogenomics knowledge of this drug and gene, "
        "write a concise clinical summary of the drug-gene interaction and actionable "
        "recommendations. Use bullet points for distinct actions. Under 200 words total."
    )
    prompt = (
        f"Drug: {drug}\n"
        f"Issue: {note}\n\n"
        f"Available pharmacogenomic context:\n{context}"
    )
    return _call_llm(system, prompt, note)


# ══════════════════════════════════════════════════════════════
# ENRICHMENT
# ══════════════════════════════════════════════════════════════

def _build_context(result: DrugResult) -> str:
    meta = result.cpic_metadata
    prof = result.pharmacogenomic_profile
    risk = result.risk_assessment
    parts = [
        f"Risk: {risk.risk_label} ({risk.severity}), confidence: {risk.confidence_score}",
        f"Gene: {prof.primary_gene}, Diplotype: {prof.diplotype}, Phenotype: {prof.phenotype}",
    ]
    if meta.guideline_name:      parts.append(f"Guideline: {meta.guideline_name}")
    if meta.drug_recommendation: parts.append(f"Recommendation: {meta.drug_recommendation}")
    if meta.classification:      parts.append(f"Classification: {meta.classification}")
    if meta.implications:
        for gene, impl in meta.implications.items():
            parts.append(f"Implication ({gene}): {impl}")
    return "\n".join(parts)


def _enrich_one(result: DrugResult):

    url     = result.cpic_metadata.guideline_url
    drug    = result.drug
    context = _build_context(result)

    if not url:
        return {"drug": drug, "explanation": _llm_fallback(drug, "none", context), "source": "llm_fallback_no_url"}

    try:
        updates = scrape_cpic_updates(url)
    except Exception as e:
        log.warning("[%s] scrape error: %s", drug, e)
        return {"drug": drug, "explanation": _llm_fallback(drug, "scrape_error", context), "source": "llm_fallback_scrape_error"}

    if not updates:
        return {"drug": drug, "explanation": _llm_fallback(drug, "no_updates", context), "source": "llm_fallback_no_updates"}

    explanation = _llm_explain(drug, updates[0]["text"])

    return {"drug": drug, "explanation": explanation, "source": "scraped"}


# ══════════════════════════════════════════════════════════════
# CORE LOGIC
# ══════════════════════════════════════════════════════════════

def run_generate_result(payload: GenerateResultRequest) -> list[PerDrugOutput]:

    timestamp = datetime.now(timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=4) as pool:
        enriched = list(pool.map(_enrich_one, payload.results))

    outputs: list[PerDrugOutput] = []

    for r, e in zip(payload.results, enriched):
        outputs.append(
            PerDrugOutput(
                patient_id=payload.patient_id,
                drug=r.drug,
                timestamp=timestamp,
                risk_assessment=r.risk_assessment,
                pharmacogenomic_profile=r.pharmacogenomic_profile,
                clinical_recommendation=ClinicalRecommendation(
                    guideline_name=r.cpic_metadata.guideline_name,
                    drug_recommendation=r.cpic_metadata.drug_recommendation,
                    classification=r.cpic_metadata.classification,
                    implications=r.cpic_metadata.implications,
                    cpic_update=e["explanation"],
                    source=e["source"],
                ),
                llm_generated_explanation=PerDrugLLMExplanation(
                    summary=e["explanation"],
                ),
                quality_metrics=payload.quality_metrics,
            )
        )

    return outputs


# ══════════════════════════════════════════════════════════════
# APPWRITE ENTRYPOINT
# ══════════════════════════════════════════════════════════════

def main(context):

    start = datetime.now()

    try:
        raw = context.req.body
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()

        data = json.loads(raw or "{}")

        payload = GenerateResultRequest(**data)

        context.log(f"Processing patient={payload.patient_id}")

        result = run_generate_result(payload)

        context.log(f"Execution time: {datetime.now()-start}")

        return context.res.json([r.model_dump() for r in result])

    except Exception as e:
        context.error(str(e))
        return context.res.json({"error": str(e)}, 500)