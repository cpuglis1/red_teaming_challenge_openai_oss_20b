"""
src/data_generation/synthea_wrapper.py
SPDX-License-Identifier: Apache-2.0

Core logic for generating synthetic patient records using Synthea and merging with non-PII mixins.
"""
import os
import subprocess
import json
from pathlib import Path
from .non_pii_mixins import generate_non_pii_tabular, generate_non_pii_unstructured, generate_other_structures

OUTPUT_DIR = Path("outputs/synthea")


def run_synthea(num_patients=10, modules=None, output_dir=OUTPUT_DIR):
    """Run Synthea to generate patient records."""
    modules = modules or []
    cmd = ["run_synthea", "-p", str(num_patients)]
    if modules:
        for m in modules:
            cmd.extend(["-m", m])
    subprocess.run(cmd, cwd=output_dir, check=True)
    # Assume Synthea outputs CSV/JSON in output_dir
    return output_dir


def load_synthea_json(output_dir=OUTPUT_DIR):
    """Load Synthea-generated JSON files."""
    records = []
    for file in Path(output_dir).glob("*.json"):
        with open(file, "r") as f:
            records.append(json.load(f))
    return records


def generate_mixed_dataset(n_patients, include_non_pii=True, seed=42, synthea_modules=None):
    """Generate mixed dataset with PII and non-PII content."""
    output_dir = Path("outputs/mixed")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_synthea(num_patients=n_patients, modules=synthea_modules, output_dir=OUTPUT_DIR)
    synthea_records = load_synthea_json(OUTPUT_DIR)
    mixed_records = []
    for rec in synthea_records:
        if include_non_pii:
            rec["vitals"] = generate_non_pii_tabular(seed)
            rec["doctor_notes"] = generate_non_pii_unstructured(seed)
            rec["billing_codes"] = generate_other_structures(seed)
        mixed_records.append(rec)
    # Save to outputs/mixed/
    out_path = output_dir / "mixed_records.json"
    with open(out_path, "w") as f:
        json.dump(mixed_records, f, indent=2)
    return out_path
