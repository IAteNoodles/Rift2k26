#!/usr/bin/env python3
"""Extract a single sample from a multi-sample VCF file."""
import sys

def extract_sample(input_vcf, output_vcf, sample_id):
    sample_idx = None
    with open(input_vcf, 'r') as fin, open(output_vcf, 'w') as fout:
        for line in fin:
            if line.startswith('##'):
                fout.write(line)
                continue
            parts = line.rstrip('\n').split('\t')
            if line.startswith('#CHROM'):
                # Find sample index
                try:
                    sample_idx = parts.index(sample_id)
                except ValueError:
                    print(f"ERROR: Sample '{sample_id}' not found in VCF header.")
                    print(f"Available samples (first 10): {parts[9:19]}")
                    sys.exit(1)
                # Write header with only this sample
                fout.write('\t'.join(parts[:9] + [sample_id]) + '\n')
                continue
            # Data line - extract only the target sample
            fout.write('\t'.join(parts[:9] + [parts[sample_idx]]) + '\n')
    print(f"Extracted sample '{sample_id}' to {output_vcf}")

if __name__ == '__main__':
    extract_sample(
        'dataset/CYP2D6_sample.vcf',
        'dataset/CYP2D6_HG00096.vcf',
        'HG00096'
    )
