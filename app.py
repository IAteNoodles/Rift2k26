"""
Unified FastAPI application — VCF-to-Diplotype pipeline.

Combines:
  Component 1  (backend.main)            — VCF ingestion & variant extraction
  Component 2  (heuristic_phasing_engine) — deterministic diplotype phasing

Endpoints:
  POST /analyze      — end-to-end: upload VCF → resolved diplotype profiles
  POST /process-vcf  — Component 1 only (standalone VCF extraction)
  POST /phase        — Component 2 only (standalone phasing from JSON)
  GET  /health       — liveness check

Run:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel, Field

from backend.main import process_vcf_bytes
from heuristic_phasing_engine import HeuristicPhasingEngine


# ══════════════════════════════════════════════════════════════════════
# Pydantic models — shared across endpoints
# ══════════════════════════════════════════════════════════════════════

# ── Variant / VCF envelope (Component 1 output) ─────────────────────

class VariantOut(BaseModel):
    gene_symbol: str
    rsid: str
    extracted_star: str
    raw_genotype_call: str


class VCFResponse(BaseModel):
    request_id: str
    vcf_valid: bool
    target_drugs: List[str]
    extracted_variants: List[VariantOut]


# ── Phasing request / response (Component 2) ────────────────────────

class PhasingRequest(BaseModel):
    request_id: str
    vcf_valid: bool
    target_drugs: List[str] = Field(default_factory=list)
    extracted_variants: List[VariantOut] = Field(default_factory=list)


class ResolvedProfile(BaseModel):
    gene: str
    diplotype: str
    contributing_rsids: List[str]
    status: str


class PhasingResponse(BaseModel):
    request_id: Optional[str]
    vcf_valid: Optional[bool]
    target_drugs: Optional[List[str]]
    resolved_profiles: List[ResolvedProfile]


# ══════════════════════════════════════════════════════════════════════
# App & engine singletons
# ══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Rift Pharmacogenomics Pipeline",
    version="1.0.0",
    description=(
        "Upload a VCF file and receive deterministic diplotype profiles. "
        "Components can also be called independently."
    ),
)

engine = HeuristicPhasingEngine()


# ══════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════

# ── End-to-end: VCF → Diplotypes ─────────────────────────────────────

@app.post("/analyze", response_model=PhasingResponse)
async def analyze(
    file: UploadFile = File(...),
    drugs: str = Form("clopidogrel,warfarin"),
):
    """Upload a VCF file and get resolved diplotype profiles in one call.

    Chains Component 1 (VCF extraction) → Component 2 (phasing engine).
    """
    content = await file.read()
    # Component 1 — extract variants
    extracted = process_vcf_bytes(content, drugs)
    # Component 2 — phase into diplotypes
    result = engine.process_payload(extracted)
    return PhasingResponse(**result)


# ── Component 1 standalone ───────────────────────────────────────────

@app.post("/process-vcf", response_model=VCFResponse)
async def process_vcf(
    file: UploadFile = File(...),
    drugs: str = Form("clopidogrel,warfarin"),
):
    """Upload a VCF file and return raw extracted variants (Component 1 only)."""
    content = await file.read()
    return process_vcf_bytes(content, drugs)


# ── Component 2 standalone ───────────────────────────────────────────

@app.post("/phase", response_model=PhasingResponse)
def phase_variants(req: PhasingRequest) -> PhasingResponse:
    """Accept extracted variants JSON and return diplotype profiles (Component 2 only)."""
    payload = req.model_dump()
    result = engine.process_payload(payload)
    return PhasingResponse(**result)


# ── Health check ─────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok"}
