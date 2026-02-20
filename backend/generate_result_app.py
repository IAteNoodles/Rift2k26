"""
Backend/generate_result_app.py  –  Standalone FastAPI wrapper for generate_result_fn.py

Run:
    python Backend/generate_result_app.py          # default port 8001
    python Backend/generate_result_app.py --port 9000

Endpoint:
    POST /generate_result   → list[PerDrugOutput]
    GET  /health            → {"status": "ok"}
    GET  /docs              → Swagger UI
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import ValidationError
    import uvicorn
except ImportError:
    sys.exit("Install with:  pip install fastapi uvicorn")

# ── import everything from the Appwrite function file ─────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

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

log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# SECTION-BY-SECTION LLM COERCION
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
            # strip accidental code fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except (json.JSONDecodeError, Exception) as e:
            if attempt == 1:
                log.warning("LLM extraction failed for %s (attempt %d): %s", field_name, attempt, e)
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
        "risk_assessment":        RiskAssessment,
        "pharmacogenomic_profile": PharmacogenomicProfile,
        "cpic_metadata":          CpicMetadata,
    }

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            name: pool.submit(_llm_extract, raw_drug, name, cls)
            for name, cls in sections.items()
        }
        extracted = {name: fut.result() for name, fut in futures.items()}

    # drug name: try common key variants
    drug_name = (
        raw_drug.get("drug")
        or raw_drug.get("drug_name")
        or raw_drug.get("medication")
        or raw_drug.get("name")
        or f"unknown_{idx}"
    )

    return {
        "drug": drug_name,
        **extracted,
    }


def _coerce_to_request(data: dict) -> GenerateResultRequest:
    """
    1. Fast path — try direct validation.
    2. On failure — extract top-level scalars directly, then run per-drug
       section extraction in parallel across all drug entries.
    """
    # ── fast path ────────────────────────────────────────────────────────────
    try:
        return GenerateResultRequest(**data)
    except (ValidationError, Exception):
        log.info("Fast-path validation failed — running LLM section extraction")

    if _groq_client is None:
        raise HTTPException(
            status_code=422,
            detail="Payload does not match schema and GROQ_API_KEY is not set for LLM coercion.",
        )

    # ── top-level scalars ─────────────────────────────────────────────────────
    patient_id = (
        data.get("patient_id")
        or data.get("patientId")
        or data.get("patient")
        or data.get("id")
        or "UNKNOWN"
    )
    engine_version = data.get("engine_version") or data.get("engineVersion")

    # quality_metrics: try direct, else default
    raw_qm = data.get("quality_metrics") or data.get("qualityMetrics") or {}
    try:
        qm = QualityMetrics(**raw_qm)
    except Exception:
        qm = QualityMetrics()

    # ── locate the list of drug results in the raw payload ───────────────────
    raw_results: list = (
        data.get("results")
        or data.get("drugs")
        or data.get("drug_results")
        or data.get("drugResults")
        or []
    )
    if not isinstance(raw_results, list):
        raw_results = [raw_results]

    # ── parallel per-drug section extraction ─────────────────────────────────
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


# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PGx Generate Result",
    description="Standalone test server for `generate_result_fn.py`",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/generate_result", response_model=list[PerDrugOutput])
async def generate_result(request: Request) -> list[PerDrugOutput]:
    try:
        body = await request.body()
        data = json.loads(body) if body.strip() else {}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    # Fast path — use directly if it already fits
    try:
        payload = GenerateResultRequest(**data)
    except Exception:
        # Doesn't fit — let LLM coerce section by section
        try:
            payload = _coerce_to_request(data)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Coercion failed: {exc}") from exc

    try:
        return run_generate_result(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health", summary="Health check")
def health() -> dict:
    return {"status": "ok"}


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket

    parser = argparse.ArgumentParser(description="Generate Result test server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    try:
        _lan_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        _lan_ip = "127.0.0.1"

    print(f"\n  Local:   http://localhost:{args.port}")
    print(f"  Network: http://{_lan_ip}:{args.port}")
    print(f"  Docs:    http://localhost:{args.port}/docs\n")
    uvicorn.run(
        "generate_result_app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=_HERE,
    )

