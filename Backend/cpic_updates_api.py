"""
Backend/cpic_updates_api.py  –  CPIC Guideline Update Enrichment API
─────────────────────────────────────────────────────────────────────
Accepts a PGx risk-assessment JSON (same schema as outputv2.json),
scrapes the CPIC guideline page for each drug that has a guideline_url,
and returns the enriched payload with the latest "Updates since
publication" block appended to every result.

Run:
    python Backend/cpic_updates_api.py          # default port 8001
    python Backend/cpic_updates_api.py --port 8002

Endpoint:
    POST /enrich
        Body  : PGxPayload  (see models below)
        Returns : EnrichedPayload

    GET  /enrich/url?url=<cpic_url>
        Returns the most recent update for a single guideline URL.
"""

from __future__ import annotations

import sys
import os
import argparse
import logging
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from groq import Groq as _Groq
    _groq_client = _Groq(api_key=os.getenv("GROQ_API_KEY", "")) if os.getenv("GROQ_API_KEY") else None
except ImportError:
    _groq_client = None

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ── path fix so we can import cpic_scraper from the project root ──────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cpic_scraper import scrape_cpic_updates, get_most_recent_update  # noqa: E402

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    sys.exit("Install with:  pip install fastapi uvicorn")

# ─── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── Pydantic models (mirror outputv2.json schema) ────────────────────────────

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

class CpicImplications(BaseModel):
    model_config = {"extra": "allow"}

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

class PGxPayload(BaseModel):
    request_id: Optional[str] = None
    timestamp: Optional[str] = None
    engine_version: Optional[str] = None
    results: list[DrugResult]

# ─── Response models ──────────────────────────────────────────────────────────

class CpicUpdate(BaseModel):
    label: str = Field(..., description="Update heading, e.g. 'January 2024 update (edited March 2024):'")
    text: str  = Field(..., description="Full text of the update block")
    pmids: list[str] = Field(default_factory=list, description="PMIDs cited in the update")

class EnrichedDrugResult(BaseModel):
    drug: str
    risk_assessment: RiskAssessment
    pharmacogenomic_profile: PharmacogenomicProfile
    cpic_metadata: CpicMetadata
    cpic_updates: list[CpicUpdate] = Field(
        default_factory=list,
        description="All update blocks scraped from the CPIC guideline page"
    )
    most_recent_update: Optional[CpicUpdate] = Field(
        None,
        description="The first (most recent) update block, or null if none found / no URL"
    )
    scrape_error: Optional[str] = Field(
        None,
        description="Error message if scraping failed"
    )

class EnrichedPayload(BaseModel):
    request_id: Optional[str] = None
    timestamp: Optional[str] = None
    engine_version: Optional[str] = None
    results: list[EnrichedDrugResult]

# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="CPIC Update Enrichment API",
    description=(
        "Enriches a PGx risk-assessment payload with the latest CPIC "
        "guideline updates scraped from cpicpgx.org."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_context(result: DrugResult) -> str:
    """Serialise a DrugResult into a plain-text block usable as LLM context."""
    meta = result.cpic_metadata
    prof = result.pharmacogenomic_profile
    risk = result.risk_assessment
    parts = [
        f"Drug: {result.drug}",
        f"Risk: {risk.risk_label} ({risk.severity}), confidence: {risk.confidence_score}",
        f"Gene: {prof.primary_gene}, Diplotype: {prof.diplotype}, Phenotype: {prof.phenotype}",
    ]
    if meta.guideline_name:
        parts.append(f"Guideline: {meta.guideline_name}")
    if meta.drug_recommendation:
        parts.append(f"Recommendation: {meta.drug_recommendation}")
    if meta.classification:
        parts.append(f"Classification: {meta.classification}")
    if meta.implications:
        for gene, impl in meta.implications.items():
            parts.append(f"Implication ({gene}): {impl}")
    return "\n".join(parts)


def _call_llm(system: str, prompt: str, drug: str, fallback: str) -> str:
    """Call Groq; return *fallback* on any failure (no Groq key, API error, etc.)."""
    if not _groq_client:
        log.warning("No Groq key – returning fallback for '%s'", drug)
        return fallback
    try:
        resp = _groq_client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("LLM call failed for '%s': %s", drug, exc)
        return fallback


def _llm_explain(drug: str, update_text: str) -> str:
    """Explain a scraped CPIC update in plain clinical language."""
    system = (
        "You are a clinical pharmacogenomics expert. "
        "Write a concise clinical summary of the CPIC guideline update below. "
        "Open with a single sentence summarising what changed, then use short bullet points "
        "for any distinct actionable items. Plain prose otherwise. Under 180 words."
    )
    prompt = f"Drug: {drug}\n\nCPIC guideline update:\n{update_text}"
    return _call_llm(system, prompt, drug, fallback=update_text)


def _llm_fallback(drug: str, context: str, reason: str, detail: str = "") -> str:
    """
    Generate a clinical explanation from full pharmacogenomics knowledge when
    scraping is not possible.
    """
    _reason_notes = {
        "no_url":       "No CPIC guideline URL is available for this drug.",
        "scrape_error": f"The CPIC guideline page could not be fetched ({detail}).",
        "no_updates":   "No 'Updates since publication' section was found on the CPIC page.",
    }
    note = _reason_notes.get(reason, "Guideline data unavailable.")
    system = (
        "You are a clinical pharmacogenomics expert. "
        "A CPIC guideline lookup encountered an issue described below. "
        "First, acknowledge the issue in one sentence. "
        "Then, using your pharmacogenomics knowledge about this drug and gene, write a concise "
        "clinical summary of the known drug-gene interaction and actionable recommendations. "
        "Use bullet points for distinct actions. Under 200 words total."
    )
    prompt = (
        f"Drug: {drug}\n"
        f"Issue: {note}\n\n"
        f"Supplementary payload context:\n{context}"
    )
    return _call_llm(system, prompt, drug, fallback=context)


# ─── URL-level cache so the same guideline page is only fetched once per call ─

def _scrape_with_cache(url: str, cache: dict[str, list[dict]]) -> tuple[list[dict], Optional[str]]:
    if url in cache:
        return cache[url], None
    try:
        updates = scrape_cpic_updates(url)
        cache[url] = updates
        log.info("Scraped %d update(s) from %s", len(updates), url)
        return updates, None
    except Exception as exc:
        log.warning("Scrape failed for %s: %s", url, exc)
        return [], str(exc)


def _to_cpic_update(raw: dict) -> CpicUpdate:
    return CpicUpdate(label=raw["label"], text=raw["text"], pmids=raw.get("pmids", []))


# ─── Per-drug enrichment with graceful degradation ────────────────────────────

_LLM_TAG = "[LLM-GENERATED] "


def _enrich_drug(
    result: DrugResult,
    url_cache: dict[str, list[dict]],
) -> tuple[str, str]:
    """
    Enrich a single DrugResult.  Returns (explanation, source_tag) where
    source_tag is one of:
        "scraped"                  – happy path: scrape + LLM explain
        "llm_fallback_no_url"      – no guideline URL in payload
        "llm_fallback_scrape_error"– URL present but page unreachable
        "llm_fallback_no_updates"  – page scraped but no update block found
    """
    drug    = result.drug
    url     = result.cpic_metadata.guideline_url
    context = _build_context(result)          # always available from payload

    # ── Case 1: no URL at all ────────────────────────────────────────────────
    if not url:
        log.info("No guideline_url for '%s' – LLM fallback from payload context.", drug)
        explanation = _llm_fallback(drug, context, reason="no_url")
        return _LLM_TAG + explanation, "llm_fallback_no_url"

    # ── Case 2: scrape the page ──────────────────────────────────────────────
    updates_raw, error = _scrape_with_cache(url, url_cache)

    if error:
        log.warning("Scrape error for '%s' (%s) – LLM fallback.", drug, error)
        explanation = _llm_fallback(drug, context, reason="scrape_error", detail=error)
        return explanation, "llm_fallback_scrape_error"

    # ── Case 3: page scraped but no updates block found ─────────────────────
    if not updates_raw:
        log.info("No updates found on page for '%s' – LLM fallback.", drug)
        explanation = _llm_fallback(drug, context, reason="no_updates")
        return explanation, "llm_fallback_no_updates"

    # ── Happy path: explain the scraped update ───────────────────────────────
    explanation = _llm_explain(drug, updates_raw[0]["text"])
    log.info("Explained scraped update for '%s'.", drug)
    return explanation, "scraped"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post(
    "/enrich",
    response_model=dict[str, str],
    summary="Enrich PGx payload with LLM-explained CPIC guideline updates",
)
async def enrich_payload(payload: PGxPayload) -> dict[str, str]:
    """
    For every drug result scrape the latest CPIC update (if a guideline_url
    is present) and return an LLM explanation.

    Drugs that have no URL, or whose page cannot be scraped, automatically
    fall back to an LLM explanation generated from the payload context;
    those entries are prefixed with ``[LLM-GENERATED]``.

    Returns ``{ drug_name: explanation }`` – always one entry per drug,
    never a 500 error due to a single bad record.
    """
    url_cache: dict[str, list[dict]] = {}
    results: dict[str, str] = {}

    for result in payload.results:
        explanation, source = _enrich_drug(result, url_cache)
        results[result.drug] = explanation
        log.info("'%s' → %s", result.drug, source)

    return results


@app.get(
    "/enrich/url",
    response_model=dict[str, str],
    summary="Scrape and explain the most recent update for a single CPIC guideline URL",
)
async def enrich_single_url(
    url: str  = Query(..., description="Full CPIC guideline URL"),
    drug: str = Query("unknown drug", description="Drug name for LLM context"),
) -> dict[str, str]:
    """
    Scrape a single CPIC URL and return an LLM explanation.
    Falls back to an LLM-generated response (tagged) if the page is
    unreachable or contains no update block – never raises a 5xx.
    """
    updates_raw, error = _scrape_with_cache(url, {})

    if error:
        log.warning("/enrich/url scrape error for '%s': %s", drug, error)
        # Build minimal context from what we have
        context = f"Drug: {drug}\nGuideline URL: {url}"
        explanation = _llm_fallback(drug, context, reason="scrape_error", detail=error)
        return {drug: _LLM_TAG + explanation}

    if not updates_raw:
        context = f"Drug: {drug}\nGuideline URL: {url}"
        explanation = _llm_fallback(drug, context, reason="no_updates")
        return {drug: _LLM_TAG + explanation}

    explanation = _llm_explain(drug, updates_raw[0]["text"])
    return {drug: explanation}


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok"}


# ─── CLI entry-point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPIC Update Enrichment API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="Port (default: 8001)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    log.info("Starting CPIC Update Enrichment API on http://%s:%d", args.host, args.port)
    uvicorn.run(
        "cpic_updates_api:app" if not args.reload else "__main__:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=os.path.dirname(os.path.abspath(__file__)),
    )
