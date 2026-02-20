"""
PharmaGuard Backend – Unified API

Single endpoint:  POST /analyze/upload
    Accepts a VCF file (multipart) + a JSON array of drug names.
    Runs PharmCAT via Docker → CPIC risk engine → LLM-enriched report generation.
    Returns a strict list[PerDrugOutput] JSON response.

Run:
    cd backend && python main.py          # default port 8000
    cd backend && python main.py --port 9000
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

# ── Local modules ───────────────────────────────────────────
from pharmcat_parser import (
    build_risk_engine_input,
    extract_genome_data,
    extract_patient_id,
    parse_results,
)
from risk_engine import DRUG_GENE_MAP, generate_risk_profiles

from generate_result_fn import (
    _groq_client,
    _GROQ_MODEL,
    CpicMetadata,
    DetectedVariant,
    DrugResult,
    GenerateResultRequest,
    PerDrugOutput,
    PharmacogenomicProfile,
    QualityMetrics,
    RiskAssessment,
    run_generate_result,
)

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmaguard")

# ── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="PharmaGuard – Unified PGx Analysis API",
    version="3.0.0",
    description=(
        "Upload a VCF file and a list of drugs. Returns strict per-drug "
        "pharmacogenomic reports with LLM-enriched clinical explanations."
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


# ══════════════════════════════════════════════════════════════
# LLM COERCION FALLBACK (from generate_result_app.py)
# ══════════════════════════════════════════════════════════════

def _llm_extract(raw: dict, field_name: str, model_class) -> dict:
    """
    Ask the LLM to extract exactly one section (field_name) from raw,
    returning a dict that satisfies model_class's JSON schema.
    Retries once on JSON parse failure.
    """
    schema = json.dumps(model_class.model_json_schema(), indent=2)
    system = (
        "You are a data normalization assistant. "
        "You will be given a raw JSON object and a target JSON schema. "
        "Extract and return ONLY the fields needed to satisfy the schema, "
        "mapping from whatever keys exist in the raw object. "
        "Return a single valid JSON object — no markdown, no code fences, no explanation."
    )
    prompt = (
        f"Target field: {field_name}\n"
        f"Target schema:\n{schema}\n\n"
        f"Raw input:\n{json.dumps(raw, indent=2)}"
    )

    for attempt in range(2):
        try:
            r = _groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.0,
                max_tokens=512,
            )
            text = r.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except (json.JSONDecodeError, Exception) as e:
            if attempt == 1:
                logger.warning("LLM extraction failed for %s (attempt %d): %s", field_name, attempt, e)
                raise
    return {}


def _coerce_drug_result(raw_drug: Any, idx: int) -> dict:
    """
    Given a raw dict that represents one drug result, extract each section
    in parallel and assemble a DrugResult-compatible dict.
    """
    if not isinstance(raw_drug, dict):
        raise ValueError(f"results[{idx}] is not an object")

    sections = {
        "risk_assessment":         RiskAssessment,
        "pharmacogenomic_profile": PharmacogenomicProfile,
        "cpic_metadata":           CpicMetadata,
    }

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            name: pool.submit(_llm_extract, raw_drug, name, cls)
            for name, cls in sections.items()
        }
        extracted = {name: fut.result() for name, fut in futures.items()}

    drug_name = (
        raw_drug.get("drug")
        or raw_drug.get("drug_name")
        or raw_drug.get("medication")
        or raw_drug.get("name")
        or f"unknown_{idx}"
    )

    return {"drug": drug_name, **extracted}


def _coerce_to_request(data: dict, patient_id: str) -> GenerateResultRequest:
    """
    LLM coercion fallback: if the risk engine output can't be directly
    validated as a GenerateResultRequest, use the LLM to extract each
    section per drug in parallel.
    """
    if _groq_client is None:
        raise HTTPException(
            status_code=422,
            detail="Payload does not match schema and GROQ_API_KEY is not set for LLM coercion.",
        )

    engine_version = data.get("engine_version") or data.get("engineVersion")

    raw_qm = data.get("quality_metrics") or data.get("qualityMetrics") or {}
    try:
        qm = QualityMetrics(**raw_qm)
    except Exception:
        qm = QualityMetrics()

    raw_results: list = (
        data.get("results")
        or data.get("drugs")
        or data.get("drug_results")
        or data.get("drugResults")
        or []
    )
    if not isinstance(raw_results, list):
        raw_results = [raw_results]

    with ThreadPoolExecutor(max_workers=min(8, len(raw_results) or 1)) as pool:
        futures = [
            pool.submit(_coerce_drug_result, raw_drug, i)
            for i, raw_drug in enumerate(raw_results)
        ]
        coerced_results = []
        for fut in futures:
            try:
                coerced_results.append(DrugResult(**fut.result()))
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"LLM coercion failed: {e}") from e

    return GenerateResultRequest(
        patient_id=patient_id,
        engine_version=engine_version,
        quality_metrics=qm,
        results=coerced_results,
    )


# ══════════════════════════════════════════════════════════════
# RISK OUTPUT → GenerateResultRequest BRIDGE
# ══════════════════════════════════════════════════════════════

def _risk_output_to_request(
    risk_output: dict,
    patient_id: str,
) -> GenerateResultRequest:
    """
    Map the deterministic risk engine output dict to a GenerateResultRequest.
    Fast path: direct Pydantic validation (the risk engine output already
    matches the DrugResult schema exactly).
    Fallback: LLM section-by-section coercion.
    """
    try:
        return GenerateResultRequest(
            patient_id=patient_id,
            engine_version=risk_output.get("engine_version"),
            quality_metrics=QualityMetrics(),
            results=[DrugResult(**r) for r in risk_output.get("results", [])],
        )
    except (ValidationError, Exception) as exc:
        logger.warning("Direct mapping failed (%s) — using LLM coercion fallback", exc)
        return _coerce_to_request(risk_output, patient_id)


# ══════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "supported_drugs": sorted(SUPPORTED_DRUGS),
    }


@app.post("/analyze/upload", response_model=list[PerDrugOutput])
async def analyze_vcf_upload(
    file: UploadFile = File(...),
    drugs: str = Form(...),
):
    """
    Upload a VCF file + drug list → strict per-drug pharmacogenomic report.

    - **file**: VCF file (.vcf, .vcf.gz, .vcf.bgz)
    - **drugs**: JSON array string, e.g. '["warfarin","simvastatin"]'

    Returns `list[PerDrugOutput]` — one entry per drug with risk assessment,
    pharmacogenomic profile, clinical recommendation, and LLM explanation.
    """
    # ── Validate file ───────────────────────────────────────
    fname = file.filename or "upload.vcf"
    if not (fname.endswith(".vcf") or fname.endswith(".vcf.gz") or fname.endswith(".vcf.bgz")):
        raise HTTPException(400, "File must be .vcf, .vcf.gz, or .vcf.bgz")

    # ── Validate drugs ──────────────────────────────────────
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

    # ── Set up temp workspace ───────────────────────────────
    job_id = uuid.uuid4().hex[:12]
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"pharmcat_{job_id}_"))
    output_dir = tmp_dir / "output"
    output_dir.mkdir()

    try:
        # Save uploaded VCF to temp dir
        vcf_path = tmp_dir / fname
        with open(vcf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # ── Stage 1: Run PharmCAT Docker ────────────────────
        try:
            _run_pharmcat(vcf_path, output_dir)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "PharmCAT timed out (>5 min)")
        except RuntimeError as e:
            raise HTTPException(500, str(e))

        # ── Stage 2: Parse PharmCAT output ──────────────────
        base_name = _strip_vcf_extension(fname)
        out_dir_str = str(output_dir)

        output_files = list(output_dir.iterdir())
        logger.info("PharmCAT output files: %s", [f.name for f in output_files])

        patient_id = extract_patient_id(out_dir_str, base_name)

        risk_input = build_risk_engine_input(
            out_dir_str, base_name,
            target_drugs=drug_list,
            request_id=job_id,
        )

        # ── Stage 3: Run CPIC risk engine ───────────────────
        risk_output = generate_risk_profiles(
            risk_input, cpic_diplotypes, cpic_recommendations
        )
        logger.info(
            "Risk engine produced %d drug result(s)",
            len(risk_output.get("results", [])),
        )

        # ── Stage 4: Map to GenerateResultRequest ───────────
        payload = _risk_output_to_request(risk_output, patient_id)

        # ── Stage 5: LLM enrichment → strict PerDrugOutput[] ─
        try:
            result = run_generate_result(payload)
        except Exception as exc:
            raise HTTPException(500, detail=f"Report generation failed: {exc}") from exc

        return result

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Run directly ────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import socket
    import uvicorn

    parser = argparse.ArgumentParser(description="PharmaGuard Unified API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    _HERE = os.path.dirname(os.path.abspath(__file__))

    try:
        _lan_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        _lan_ip = "127.0.0.1"

    print(f"\n  Local:   http://localhost:{args.port}")
    print(f"  Network: http://{_lan_ip}:{args.port}")
    print(f"  Docs:    http://localhost:{args.port}/docs\n")

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=_HERE,
    )
