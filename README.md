# Component 1: Synchronous Data Ingestion & Gateway Validation

This component serves as the high-throughput entry point for the PharmaGuard system. It is responsible for ingesting, validating, and parsing patient VCF (Variant Call Format) files to extract critical pharmacogenomic variants.

## Features

*   **Synchronous Processing:** Built with `FastAPI` to provide sub-second response times for live demonstrations.
*   **VCF Parsing:** efficient parsing logic (using `vcfpy`) to extract `GENE`, `STAR`, and `RS` information.
*   **Strict Output Schema:** Returns a standardized JSON payload compatible with downstream clinical decision support systems.
*   **Demo Mode:** Includes fallback logic to ensure successful demonstration even with raw or unannotated VCF sample files.

## Tech Stack

*   **Language:** Python 3.13+
*   **Framework:** FastAPI
*   **Parsing Library:** vcfpy
*   **Server:** Uvicorn

## API Specification

### Endpoint: `POST /process-vcf`

Accepts a VCF file upload and returns extracted pharmacogenomic variants.

**Request:**
*   `file`: The `.vcf` or `.vcf.gz` file (multipart/form-data).
*   `drugs`: (Optional) Comma-separated list of target drugs (default: "clopidogrel, warfarin").

**Response (JSON):**

```json
{
  "request_id": "req-98765-demo",
  "vcf_valid": true,
  "target_drugs": ["clopidogrel", "warfarin"],
  "extracted_variants": [
    {
      "gene_symbol": "CYP2C19",
      "rsid": "rs12248560",
      "extracted_star": "*2",
      "raw_genotype_call": "1|1"
    },
    {
      "gene_symbol": "CYP2C19",
      "rsid": "rs28399504",
      "extracted_star": "*17",
      "raw_genotype_call": "0/1"
    },
    {
      "gene_symbol": "VKORC1",
      "rsid": "rs9923231",
      "extracted_star": "Unknown",
      "raw_genotype_call": "1/1"
    }
  ]
}
```

## Running the Component

1.  **Install Dependencies:**
    ```bash
    pip install fastapi uvicorn vcfpy python-multipart
    ```

2.  **Start the Server:**
    ```bash
    python -m uvicorn backend.main:app --reload --port 8001
    ```

3.  **Access Documentation:**
    Open your browser to: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

4.  **Test:**
    Use the Swagger UI or `curl` to upload a sample VCF file.
