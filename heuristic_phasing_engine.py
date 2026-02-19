"""
HeuristicPhasingEngine — Zero-dependency, deterministic diplotype phasing.

Accepts a pharmacogenomic request envelope containing extracted VCF variants,
groups them by gene, routes each gene through three strictly-ordered processors,
and returns a response envelope with resolved diplotype profiles.
"""


class HeuristicPhasingEngine:
    """Deterministic heuristic phasing engine for pharmacogenomic diplotyping.

    Processes a payload of extracted genetic variants and synthesises a final
    diplotype string per gene using three strictly-ordered routing rules:

        1. Deterministic Phased Processor   — triggered by "|" in genotype call
        2. Unphased Heterozygous Processor  — single "/" het variant
        3. Conservative Fallback Processor  — multiple "/" variants (trans assumption)

    All star-allele values are used as-is from the input (no '*' prefix added).
    Variants with extracted_star == "Unknown" are processed normally but the
    gene's profile is flagged with status "uncertain".
    """

    __slots__ = ()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_payload(self, payload: dict) -> dict:
        """Process a full request envelope and return resolved profiles.

        Parameters
        ----------
        payload : dict
            Must contain at minimum ``"extracted_variants"`` (list[dict]).
            May also contain ``"request_id"``, ``"vcf_valid"``,
            ``"target_drugs"`` which will be echoed in the response.

        Returns
        -------
        dict
            Response envelope with echoed metadata and ``"resolved_profiles"``.
        """
        # --- Echo metadata ------------------------------------------------
        response: dict = {
            "request_id": payload.get("request_id"),
            "vcf_valid": payload.get("vcf_valid"),
            "target_drugs": payload.get("target_drugs"),
        }

        variants = payload.get("extracted_variants")
        if not variants:
            response["resolved_profiles"] = []
            return response

        # --- Group by gene (single pass) ----------------------------------
        gene_map: dict = {}          # gene -> list[dict]
        gene_rsids: dict = {}        # gene -> list[str]  (insertion order)
        gene_uncertain: dict = {}    # gene -> bool

        for v in variants:
            gene = v["gene_symbol"]
            gene_map.setdefault(gene, []).append(v)
            gene_rsids.setdefault(gene, []).append(v["rsid"])
            if v["extracted_star"] == "Unknown":
                gene_uncertain[gene] = True

        # --- Route each gene ----------------------------------------------
        profiles: list = []
        for gene in gene_map:
            chrom_a, chrom_b = self._route_gene(gene_map[gene])
            diplotype = self._assemble_diplotype(chrom_a, chrom_b)
            profiles.append({
                "gene": gene,
                "diplotype": diplotype,
                "contributing_rsids": gene_rsids[gene],
                "status": "uncertain" if gene_uncertain.get(gene) else "resolved",
            })

        # Deterministic ordering by gene name
        profiles.sort(key=lambda p: p["gene"])
        response["resolved_profiles"] = profiles
        return response

    # ------------------------------------------------------------------
    # Internal routing
    # ------------------------------------------------------------------

    def _route_gene(self, variants: list) -> tuple:
        """Partition variants into phased / unphased and delegate."""
        phased: list = []
        unphased: list = []

        for v in variants:
            call = v["raw_genotype_call"]
            if "|" in call:
                phased.append(v)
            elif "/" in call:
                unphased.append(v)
            # else: unrecognised separator — silently skip

        chrom_a: list = []
        chrom_b: list = []

        # Processor 1 — Deterministic Phased
        if phased:
            self._process_phased(phased, chrom_a, chrom_b)

        # Processor 2 / 3 — Unphased branch
        if unphased:
            self._process_unphased(unphased, chrom_a, chrom_b)

        return chrom_a, chrom_b

    # ------------------------------------------------------------------
    # Processor 1 — Deterministic Phased ("|" trigger)
    # ------------------------------------------------------------------

    @staticmethod
    def _process_phased(variants: list, chrom_a: list, chrom_b: list) -> None:
        for v in variants:
            left, right = v["raw_genotype_call"].split("|", 1)
            star = v["extracted_star"]
            if left != "0":
                chrom_a.append(star)
            if right != "0":
                chrom_b.append(star)

    # ------------------------------------------------------------------
    # Processor 2 & 3 — Unphased ("/" trigger)
    # ------------------------------------------------------------------

    @staticmethod
    def _process_unphased(variants: list, chrom_a: list, chrom_b: list) -> None:
        if len(variants) == 1:
            # --- Processor 2: single unphased variant ---------------------
            v = variants[0]
            parts = v["raw_genotype_call"].split("/", 1)
            star = v["extracted_star"]
            left_nonzero = parts[0] != "0"
            right_nonzero = parts[1] != "0"

            if left_nonzero and right_nonzero:
                # Homozygous alt (e.g. "1/1") → both chromosomes
                chrom_a.append(star)
                chrom_b.append(star)
            elif left_nonzero or right_nonzero:
                # Heterozygous (e.g. "0/1" or "1/0") → mutation to A only
                chrom_a.append(star)
            # else: "0/0" → reference, skip
        else:
            # --- Processor 3: conservative fallback (trans assumption) ----
            for idx, v in enumerate(variants):
                parts = v["raw_genotype_call"].split("/", 1)
                star = v["extracted_star"]
                left_nonzero = parts[0] != "0"
                right_nonzero = parts[1] != "0"

                if left_nonzero and right_nonzero:
                    # Hom-alt within multi-unphased → both chromosomes
                    chrom_a.append(star)
                    chrom_b.append(star)
                elif left_nonzero or right_nonzero:
                    # Het → round-robin assignment (trans)
                    if idx % 2 == 0:
                        chrom_a.append(star)
                    else:
                        chrom_b.append(star)
                # else: "0/0" → skip

    # ------------------------------------------------------------------
    # Diplotype assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _assemble_diplotype(chrom_a: list, chrom_b: list) -> str:
        _star = lambda v: v if v.startswith("*") else "*" + v
        a = "+".join(_star(v) for v in chrom_a) if chrom_a else "*1"
        b = "+".join(_star(v) for v in chrom_b) if chrom_b else "*1"
        return a + "/" + b


# ======================================================================
# CLI — accepts JSON input, returns JSON output
# ======================================================================

if __name__ == "__main__":
    import json
    import sys

    # Usage:
    #   echo '{ ... }' | python heuristic_phasing_engine.py
    #   python heuristic_phasing_engine.py input.json
    #   python heuristic_phasing_engine.py input.json -o output.json

    def _read_input() -> dict:
        args = sys.argv[1:]
        src = None
        for a in args:
            if a != "-o" and src is None and not a.startswith("-"):
                src = a
                break

        if src:
            with open(src, "r") as f:
                return json.load(f)
        else:
            return json.load(sys.stdin)

    def _write_output(data: dict) -> None:
        args = sys.argv[1:]
        dest = None
        for i, a in enumerate(args):
            if a == "-o" and i + 1 < len(args):
                dest = args[i + 1]
                break

        text = json.dumps(data, indent=2) + "\n"
        if dest:
            with open(dest, "w") as f:
                f.write(text)
            print(f"Output written to {dest}", file=sys.stderr)
        else:
            sys.stdout.write(text)

    payload = _read_input()
    engine = HeuristicPhasingEngine()
    result = engine.process_payload(payload)
    _write_output(result)
