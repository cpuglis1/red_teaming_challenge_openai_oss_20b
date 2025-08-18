import json, re
from pathlib import Path
from scripts._formats import (
    render_note, render_csv_labs, render_csv_meds, render_csv_vitals,
    render_hl7, render_fhir, render_cda, render_email, render_ics
)

def _fake_meta():
    return {
        "name": "Michael Santiago",
        "dob": "1977-08-20",
        "address": "283 Steven Groves, Lake Mark, WI 07832",
        "email": "michael.santiago@example.com",
        "phone": "(555) 325-8359",
        "mrn": "MRN-717889",
        "ssn": "384-10-3615"
    }


def test_renderers_write_files(tmp_path):
    m = _fake_meta()
    rng = __import__("random").Random(123)
    scenarios = ["control", "eval_gov", "live_gov", "hidden_eval", "hidden_live"]
    formats = [
        (render_note, tmp_path/"notes", 0),
        (render_csv_labs, tmp_path/"tables", None),
        (render_csv_meds, tmp_path/"tables", None),
        (render_csv_vitals, tmp_path/"tables", None),
        (render_hl7, tmp_path/"hl7", None),
        (render_fhir, tmp_path/"fhir", None),
        (render_cda, tmp_path/"cda", None),
        (render_email, tmp_path/"email", None),
        (render_ics, tmp_path/"calendar", None),
    ]
    for scenario in scenarios:
        for func, out_dir, idx in formats:
            if func == render_note:
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = func(m, out_dir, idx if idx is not None else 0, scenario, rng)
            elif func == render_email:
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = func(m, out_dir, scenario, rng)
            else:
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = func(m, out_dir, rng)
            p = Path(file_path)
            assert p.exists(), f"{file_type} not written"
            assert isinstance(text, str) and len(text) > 20
            # At least some PII appears
            assert any(m["name"].split()[0] in text for _ in [0]) or any(s["type"]=="NAME" for s in pii_spans)
            # Offsets sane
            for s in pii_spans:
                assert 0 <= s["start"] < s["end"] <= len(text)
            # Decoy span structure
            for d in decoy_spans:
                assert "start" in d and "end" in d
