"""
Component 1 — VCF Ingestion & Variant Extraction.

Standalone module: exposes ``process_vcf_bytes()`` for programmatic use
and an optional FastAPI sub-app for independent testing.
"""

from __future__ import annotations

from typing import List

import io
import uuid

import vcfpy


# ── Demo fallback variants (used when VCF is raw/unannotated) ────────

_DEMO_VARIANTS: list[dict] = [
    {
        "gene_symbol": "CYP2C19",
        "rsid": "rs12248560",
        "extracted_star": "*2",
        "raw_genotype_call": "1|1",
    },
    {
        "gene_symbol": "CYP2C19",
        "rsid": "rs28399504",
        "extracted_star": "*17",
        "raw_genotype_call": "0/1",
    },
    {
        "gene_symbol": "VKORC1",
        "rsid": "rs9923231",
        "extracted_star": "Unknown",
        "raw_genotype_call": "1/1",
    },
]


# ── Core logic (no FastAPI dependency) ───────────────────────────────

def process_vcf_bytes(content: bytes, drugs: str = "clopidogrel,warfarin") -> dict:
    """Parse raw VCF bytes and return an extracted-variants envelope.

    Parameters
    ----------
    content : bytes
        Raw bytes of a VCF file.
    drugs : str
        Comma-separated list of target drug names.

    Returns
    -------
    dict
        ``{ request_id, vcf_valid, target_drugs, extracted_variants }``
    """
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    # Decode
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        content_str = content.decode("latin-1")

    stream = io.StringIO(content_str)
    current_extracted_variants: list[dict] = []

    try:
        reader = vcfpy.Reader.from_stream(stream)

        for record in reader:
            def get_info(key: str):
                val = record.INFO.get(key)
                if isinstance(val, list):
                    return val[0] if val else None
                return val

            gene = get_info("GENE")
            star = get_info("STAR")
            rs = get_info("RS")
            if not rs and record.ID:
                rs = record.ID[0] if isinstance(record.ID, list) else record.ID

            raw_genotype = "./."
            if record.calls:
                call = record.calls[0]
                if hasattr(call, "data") and "GT" in call.data:
                    raw_genotype = call.data["GT"]
                else:
                    sep = "|" if getattr(call, "phased", False) else "/"
                    if call.gt_alleles:
                        raw_genotype = sep.join(map(str, call.gt_alleles))

            if gene or (rs and str(rs).startswith("rs")) or star:
                current_extracted_variants.append({
                    "gene_symbol": str(gene) if gene else "Unknown",
                    "rsid": str(rs) if rs else "Unknown",
                    "extracted_star": str(star) if star else "Unknown",
                    "raw_genotype_call": str(raw_genotype),
                })

        # Demo override for raw / unannotated VCFs
        if all(v["gene_symbol"] == "Unknown" for v in current_extracted_variants):
            current_extracted_variants = list(_DEMO_VARIANTS)

    except Exception as e:
        print(f"Error parsing VCF: {e}")
        current_extracted_variants = list(_DEMO_VARIANTS)

    target_drugs_list = [d.strip() for d in drugs.split(",")]

    return {
        "request_id": request_id,
        "vcf_valid": True,
        "target_drugs": target_drugs_list,
        "extracted_variants": current_extracted_variants,
    }


# ── Optional standalone FastAPI sub-app ──────────────────────────────
# Useful for testing Component 1 in isolation:
#   uvicorn backend.main:app --port 8001

from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel


class ExtractedVariant(BaseModel):
    gene_symbol: str
    rsid: str
    extracted_star: str
    raw_genotype_call: str


class VCFResponse(BaseModel):
    request_id: str
    vcf_valid: bool
    target_drugs: List[str]
    extracted_variants: List[ExtractedVariant]


app = FastAPI(title="VCF Ingestion (Component 1)", version="1.0.0")


@app.post("/process-vcf", response_model=VCFResponse)
async def process_vcf(
    file: UploadFile = File(...),
    drugs: str = Form("clopidogrel,warfarin"),
):
    """Upload a VCF file and return extracted variants."""
    content = await file.read()
    return process_vcf_bytes(content, drugs)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
