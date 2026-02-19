"""
PharmaGuard Backend – FastAPI endpoint for VCF → PharmCAT → Risk analysis pipeline.

Accepts a VCF file upload + a JSON array of drug names, runs PharmCAT via Docker,
maps genotype calls through the CPIC-based risk engine, and returns a unified JSON
with patient ID, genome data, drug-level recommendations, and risk levels.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pharmcat_parser import (
    build_risk_engine_input,
    extract_genome_data,
    extract_patient_id,
    parse_results,
)
from risk_engine import DRUG_GENE_MAP, generate_risk_profiles

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmaguard")

# ── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="PharmaGuard – PharmCAT Risk Analysis API",
    version="2.0.0",
    description=(
        "Upload a VCF file and a list of drugs. Returns patient genome data, "
        "CPIC-based risk assessments, and clinical recommendations."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ───────────────────────────────────────────
DOCKER_IMAGE = os.getenv("PHARMCAT_DOCKER_IMAGE", "pgkb/pharmcat")
DATA_DIR = Path(__file__).resolve().parent / "data"

GENE_FILES = {
    "CYP2D6": "diplotype_CYP2D6.json",
    "CYP2C19": "diplotype_CYP2C19.json",
    "CYP2C9": "diplotype_CYP2C9.json",
    "SLCO1B1": "diplotype_SLCO1B1.json",
    "TPMT": "diplotype_TPMT.json",
    "DPYD": "diplotype_DPYD.json",
}

# Supported drugs (lowercase) – only these are accepted
SUPPORTED_DRUGS: set[str] = {d.lower() for d in DRUG_GENE_MAP}


# ── Load CPIC reference data at module level ────────────────
def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


logger.info("Loading CPIC reference data …")
cpic_diplotypes: dict[str, list[dict]] = {}
for gene, fname in GENE_FILES.items():
    fpath = DATA_DIR / fname
    cpic_diplotypes[gene] = _load_json(fpath)
    logger.info("  %s: %d entries", gene, len(cpic_diplotypes[gene]))

cpic_recommendations: list[dict] = _load_json(DATA_DIR / "cpic_recommendations.json")
logger.info("  Recommendations: %d entries", len(cpic_recommendations))
logger.info("CPIC data loaded ✓")


# ── PharmCAT Docker runner ──────────────────────────────────
def _run_pharmcat(vcf_path: Path, output_dir: Path) -> None:
    """
    Run PharmCAT pipeline via Docker.
    Mounts the parent directory into the container and writes output to output_dir.
    """
    parent = vcf_path.parent
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{parent}:/data",
        DOCKER_IMAGE,
        "pharmcat_pipeline",
        f"/data/{vcf_path.name}",
        "-o", "/data/output",
        "-reporterJson",
    ]
    logger.info("Running PharmCAT: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"PharmCAT failed (exit {result.returncode}).\n"
            f"stderr: {result.stderr[-2000:]}\n"
            f"stdout: {result.stdout[-1000:]}"
        )


def _strip_vcf_extension(fname: str) -> str:
    """Strip the VCF-family extensions to get the base name PharmCAT uses."""
    for suffix in (".vcf.bgz", ".vcf.gz", ".vcf"):
        if fname.endswith(suffix):
            return fname[: -len(suffix)]
    return fname


# ── Request schema ──────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """JSON body for POST /analyze."""
    vcf_path: str = Field(
        ...,
        description="Absolute path to a VCF file on the server (.vcf, .vcf.gz, .vcf.bgz)",
        examples=["/data/patients/PATIENT_001.vcf"],
    )
    drugs: list[str] = Field(
        ...,
        min_length=1,
        description="List of drug names to evaluate",
        examples=[["warfarin", "simvastatin", "clopidogrel"]],
    )


# ── Endpoints ───────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "supported_drugs": sorted(SUPPORTED_DRUGS),
    }


@app.post("/analyze")
async def analyze_vcf(req: AnalyzeRequest):
    """
    Analyse a VCF file and return a unified pharmacogenomics risk report.

    **Request body (JSON):**
    ```json
    {
      "vcf_path": "/path/to/patient.vcf",
      "drugs": ["warfarin", "simvastatin", "clopidogrel"]
    }
    ```

    **Response:** patient_id, job_id, genome_data, drug_results, metadata
    """

    # ── Validate VCF path ───────────────────────────────────
    vcf_file = Path(req.vcf_path).resolve()
    if not vcf_file.exists():
        raise HTTPException(404, f"VCF file not found: {req.vcf_path}")

    fname = vcf_file.name
    if not (fname.endswith(".vcf") or fname.endswith(".vcf.gz") or fname.endswith(".vcf.bgz")):
        raise HTTPException(400, "File must be .vcf, .vcf.gz, or .vcf.bgz")

    # ── Validate drugs ──────────────────────────────────────
    drug_list = [d.strip().lower() for d in req.drugs if d.strip()]
    if not drug_list:
        raise HTTPException(400, "At least one drug must be specified")

    unsupported = [d for d in drug_list if d not in SUPPORTED_DRUGS]
    if unsupported:
        raise HTTPException(
            400,
            f"Unsupported drug(s): {unsupported}. Supported: {sorted(SUPPORTED_DRUGS)}",
        )

    # ── Set up temp workspace ───────────────────────────────
    job_id = uuid.uuid4().hex[:12]
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"pharmcat_{job_id}_"))
    output_dir = tmp_dir / "output"
    output_dir.mkdir()

    try:
        # Copy VCF into temp dir (PharmCAT Docker needs a mounted dir)
        dest_vcf = tmp_dir / fname
        shutil.copy2(vcf_file, dest_vcf)

        # ── Run PharmCAT Docker ─────────────────────────────
        try:
            _run_pharmcat(dest_vcf, output_dir)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "PharmCAT timed out (>5 min)")
        except RuntimeError as e:
            raise HTTPException(500, str(e))

        # ── Process results ─────────────────────────────────
        base_name = _strip_vcf_extension(fname)
        out_dir_str = str(output_dir)

        output_files = list(output_dir.iterdir())
        logger.info("PharmCAT output files: %s", [f.name for f in output_files])

        patient_id = extract_patient_id(out_dir_str, base_name)
        genome_data = extract_genome_data(out_dir_str, base_name)

        risk_input = build_risk_engine_input(
            out_dir_str, base_name,
            target_drugs=drug_list,
            request_id=job_id,
        )
        risk_output = generate_risk_profiles(
            risk_input, cpic_diplotypes, cpic_recommendations
        )

        pharmcat_summary = parse_results(
            out_dir_str, base_name,
            drug_filter=[d.lower() for d in drug_list],
        )

        response = _build_response(
            patient_id=patient_id,
            job_id=job_id,
            genome_data=genome_data,
            risk_output=risk_output,
            pharmcat_summary=pharmcat_summary,
        )

        return JSONResponse(content=response)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/analyze/upload")
async def analyze_vcf_upload(
    file: UploadFile = File(...),
    drugs: str = Form(...),
):
    """
    Upload a VCF file via multipart form-data (legacy endpoint).

    - **file**: VCF file (.vcf, .vcf.gz, .vcf.bgz)
    - **drugs**: JSON array string, e.g. '["warfarin","simvastatin"]'
    """
    fname = file.filename or "upload.vcf"
    if not (fname.endswith(".vcf") or fname.endswith(".vcf.gz") or fname.endswith(".vcf.bgz")):
        raise HTTPException(400, "File must be .vcf, .vcf.gz, or .vcf.bgz")

    try:
        drug_list_raw: list[str] = json.loads(drugs)
        if not isinstance(drug_list_raw, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(400, 'drugs must be a JSON array, e.g. ["warfarin","codeine"]')

    drug_list = [d.strip().lower() for d in drug_list_raw if d.strip()]
    if not drug_list:
        raise HTTPException(400, "At least one drug must be specified")

    unsupported = [d for d in drug_list if d not in SUPPORTED_DRUGS]
    if unsupported:
        raise HTTPException(
            400,
            f"Unsupported drug(s): {unsupported}. Supported: {sorted(SUPPORTED_DRUGS)}",
        )

    job_id = uuid.uuid4().hex[:12]
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"pharmcat_{job_id}_"))
    output_dir = tmp_dir / "output"
    output_dir.mkdir()

    try:
        vcf_path = tmp_dir / fname
        with open(vcf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            _run_pharmcat(vcf_path, output_dir)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "PharmCAT timed out (>5 min)")
        except RuntimeError as e:
            raise HTTPException(500, str(e))

        base_name = _strip_vcf_extension(fname)
        out_dir_str = str(output_dir)

        output_files = list(output_dir.iterdir())
        logger.info("PharmCAT output files: %s", [f.name for f in output_files])

        patient_id = extract_patient_id(out_dir_str, base_name)
        genome_data = extract_genome_data(out_dir_str, base_name)
        risk_input = build_risk_engine_input(
            out_dir_str, base_name,
            target_drugs=drug_list,
            request_id=job_id,
        )
        risk_output = generate_risk_profiles(
            risk_input, cpic_diplotypes, cpic_recommendations
        )
        pharmcat_summary = parse_results(
            out_dir_str, base_name,
            drug_filter=[d.lower() for d in drug_list],
        )

        response = _build_response(
            patient_id=patient_id,
            job_id=job_id,
            genome_data=genome_data,
            risk_output=risk_output,
            pharmcat_summary=pharmcat_summary,
        )

        return JSONResponse(content=response)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _build_response(
    *,
    patient_id: str,
    job_id: str,
    genome_data: list[dict],
    risk_output: dict,
    pharmcat_summary: dict,
) -> dict:
    """
    Merge risk engine output + PharmCAT parsed data into the unified response.
    """
    drug_results = []
    for r in risk_output.get("results", []):
        drug_name = r["drug"]

        # Find matching PharmCAT recommendations for this drug
        pharmcat_recs = [
            rec for rec in pharmcat_summary.get("recommendations", [])
            if rec.get("drug", "").lower() == drug_name.lower()
        ]

        drug_entry = {
            "drug": drug_name,
            "risk_assessment": r.get("risk_assessment", {}),
            "pharmacogenomic_profile": r.get("pharmacogenomic_profile", {}),
            "recommendations": r.get("cpic_metadata", {}),
            "pharmcat_annotations": pharmcat_recs[:3] if pharmcat_recs else [],
        }
        drug_results.append(drug_entry)

    return {
        "patient_id": patient_id,
        "job_id": job_id,
        "genome_data": genome_data,
        "drug_results": drug_results,
        "metadata": {
            "pharmcat_version": pharmcat_summary.get("metadata", {}).get("pharmcatVersion"),
            "data_version": pharmcat_summary.get("metadata", {}).get("dataVersion"),
            "engine_version": risk_output.get("engine_version", "1.0.0"),
            "timestamp": risk_output.get("timestamp"),
            "genes_called": pharmcat_summary.get("calledGeneCount", 0),
            "genes_uncalled": pharmcat_summary.get("uncalledGenes", []),
        },
    }


# ── Run directly ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
