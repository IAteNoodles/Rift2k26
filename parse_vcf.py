"""
CYP2D6 VCF Parser using cyvcf2
Parses dataset/CYP2D6_sample.vcf from 1000 Genomes Phase 3
"""

from cyvcf2 import VCF
import numpy as np
import sys

VCF_PATH    = "dataset/CYP2D6_sample.vcf"
OUTPUT_PATH = "output/vcf_parse_results.txt"

import os
os.makedirs("output", exist_ok=True)

vcf = VCF(VCF_PATH)

# Tee output: write to both the file and stdout
_file = open(OUTPUT_PATH, "w")

def log(*args, **kwargs):
    print(*args, **kwargs)
    print(*args, **kwargs, file=_file)

# ── Header info ────────────────────────────────────────────────────────────────
log("=" * 60)
log("VCF HEADER INFORMATION")
log("=" * 60)
log(f"Samples : {len(vcf.samples)}")
log(f"First 5 samples: {vcf.samples[:5]}")

# ── Per-variant parsing ────────────────────────────────────────────────────────
log("\n" + "=" * 60)
log("VARIANT DETAILS")
log("=" * 60)

variant_records = []

for variant in vcf:
    record = {
        "chrom":      variant.CHROM,
        "pos":        variant.POS,          # 1-based
        "start":      variant.start,        # 0-based (htslib convention)
        "id":         variant.ID or ".",
        "ref":        variant.REF,
        "alt":        variant.ALT,
        "qual":       variant.QUAL,
        "filter":     variant.FILTER,

        # INFO fields present in this VCF
        "AC":         variant.INFO.get("AC"),
        "AF":         variant.INFO.get("AF"),
        "AN":         variant.INFO.get("AN"),
        "NS":         variant.INFO.get("NS"),
        "DP":         variant.INFO.get("DP"),
        "VT":         variant.INFO.get("VT"),
        "AA":         variant.INFO.get("AA"),
        "EAS_AF":     variant.INFO.get("EAS_AF"),
        "EUR_AF":     variant.INFO.get("EUR_AF"),
        "AFR_AF":     variant.INFO.get("AFR_AF"),
        "AMR_AF":     variant.INFO.get("AMR_AF"),
        "SAS_AF":     variant.INFO.get("SAS_AF"),

        # Genotype arrays (numpy)
        # gt_types: 0=HOM_REF, 1=HET, 2=UNKNOWN, 3=HOM_ALT
        "gt_types":   variant.gt_types,
    }
    variant_records.append(record)

    # ── Print one block per variant ──
    log(f"\nVariant  : {record['chrom']}:{record['pos']}  {record['ref']} → {record['alt']}")
    log(f"  ID     : {record['id']}")
    log(f"  QUAL   : {record['qual']}  |  FILTER: {record['filter']}")
    log(f"  Type   : {record['VT']}")
    log(f"  AC/AN  : {record['AC']} / {record['AN']}   (AF={record['AF']:.6f})")
    log(f"  DP     : {record['DP']}")
    log(f"  Anc.   : {record['AA']}")
    log("  Pop AF :")
    log(f"    EAS={record['EAS_AF']}  EUR={record['EUR_AF']}")
    log(f"    AFR={record['AFR_AF']}  AMR={record['AMR_AF']}  SAS={record['SAS_AF']}")

    gt = record["gt_types"]
    n_hom_ref = int(np.sum(gt == 0))
    n_het     = int(np.sum(gt == 1))
    n_unknown = int(np.sum(gt == 2))
    n_hom_alt = int(np.sum(gt == 3))
    log(f"  Genotype counts (of {len(gt)} samples):")
    log(f"    HOM_REF={n_hom_ref}  HET={n_het}  UNKNOWN={n_unknown}  HOM_ALT={n_hom_alt}")

# ── Summary ────────────────────────────────────────────────────────────────────
log("\n" + "=" * 60)
log("SUMMARY")
log("=" * 60)
log(f"Total variants parsed : {len(variant_records)}")

# Allele frequency across all variants
afs = [r["AF"] for r in variant_records if r["AF"] is not None]
log(f"AF range              : {min(afs):.6f} – {max(afs):.6f}")

# Genotype type totals across all variants
all_gt = np.concatenate([r["gt_types"] for r in variant_records])
log(f"HOM_REF calls : {int(np.sum(all_gt == 0))}")
log(f"HET calls     : {int(np.sum(all_gt == 1))}")
log(f"UNKNOWN calls : {int(np.sum(all_gt == 2))}")
log(f"HOM_ALT calls : {int(np.sum(all_gt == 3))}")

vcf.close()
log(f"\nOutput written to {OUTPUT_PATH}")
_file.close()
