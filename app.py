"""
FastAPI wrapper for HeuristicPhasingEngine.

Run:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000

POST JSON to:
    http://localhost:8000/phase
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from heuristic_phasing_engine import HeuristicPhasingEngine


# ── Pydantic models (request) ────────────────────────────────────────

class VariantIn(BaseModel):
    gene_symbol: str
    rsid: str
    extracted_star: str
    raw_genotype_call: str


class PhasingRequest(BaseModel):
    request_id: str
    vcf_valid: bool
    target_drugs: List[str] = Field(default_factory=list)
    extracted_variants: List[VariantIn] = Field(default_factory=list)


# ── Pydantic models (response) ───────────────────────────────────────

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


# ── App & engine ─────────────────────────────────────────────────────

app = FastAPI(
    title="HeuristicPhasingEngine API",
    version="1.0.0",
    description="Deterministic diplotype phasing from extracted VCF variants.",
)

engine = HeuristicPhasingEngine()


@app.post("/phase", response_model=PhasingResponse)
def phase_variants(req: PhasingRequest) -> PhasingResponse:
    """Accept a phasing request and return resolved diplotype profiles."""
    payload = req.model_dump()
    result = engine.process_payload(payload)
    return PhasingResponse(**result)


@app.get("/health")
def health_check():
    return {"status": "ok"}
