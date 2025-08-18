from pathlib import Path
import json

def test_spans_align_to_text(tmp_path):
    # Use an existing small bundle or synthesize a tiny note with known meta
    from scripts._formats import render_note, render_csv_labs, render_fhir, render_cda, render_email, render_ics
    rng = __import__("random").Random(123)
    meta = {
        "name":"Barbara Sanchez","dob":"1959-09-14",
        "address":"3116 Henderson Mountain Apt. 106, Laurenville, IA 25613",
        "email":"barbara.sanchez@example.com","phone":"(555) 801-6313",
        "mrn":"MRN-983794","ssn":"886-17-4752"
    }
    # Note
    text, fpath, ftype, blocks, pii_spans, decoy_spans = render_note(meta, tmp_path/"notes", 0, "control", rng)
    for s in pii_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
    for s in decoy_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
    # CSV (labs)
    text, fpath, ftype, blocks, pii_spans, decoy_spans = render_csv_labs(meta, tmp_path/"csvs", rng)
    for s in pii_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
    # FHIR
    text, fpath, ftype, blocks, pii_spans, decoy_spans = render_fhir(meta, tmp_path/"fhir", rng)
    for s in pii_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
    # CDA
    text, fpath, ftype, blocks, pii_spans, decoy_spans = render_cda(meta, tmp_path/"cda", rng)
    for s in pii_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
    # Email
    text, fpath, ftype, blocks, pii_spans, decoy_spans = render_email(meta, tmp_path/"email", "control", rng)
    for s in pii_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
    # ICS
    text, fpath, ftype, blocks, pii_spans, decoy_spans = render_ics(meta, tmp_path/"ics", rng)
    for s in pii_spans:
        frag = text[s["start"]:s["end"]]
        assert len(frag) > 0
