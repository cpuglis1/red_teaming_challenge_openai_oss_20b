"""
Automated tests for synthetic + PII-mixed data generation.
"""
import os
from src import generate_mixed_dataset

def test_generate_mixed_dataset():
    out_path = generate_mixed_dataset(n_patients=2, include_non_pii=True, seed=99)
    assert os.path.exists(out_path), "Output file not created"
    import json
    with open(out_path) as f:
        records = json.load(f)
    assert len(records) > 0, "No records generated"
    for rec in records:
        assert "vitals" in rec, "Vitals missing"
        assert "doctor_notes" in rec, "Doctor notes missing"
        assert "billing_codes" in rec or "encounter_summary" in rec, "Billing/encounter missing"
        assert "name" in rec or "FIRST" in rec, "PII missing"
