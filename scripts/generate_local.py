"""
scripts/generate_local.py
SPDX-License-Identifier: Apache-2.0

Local-only synthetic PII dataset generator (no Synthea).
- Creates realistic person + encounter text
- Seeds PII spans (NAME, DOB, EMAIL, PHONE, ADDRESS, MRN, SSN-like)
- Mixes in non-PII clinical content (tables, FHIR-ish JSON, HL7-ish, headers, code fences)
- Adds decoy look-alikes (ORDER #123-45-6789) to measure over-redaction
- Produces variants: plain, formatted, obfuscated, mixed
- Writes data/items.jsonl matching src/pii_eval_awareness/data/schema.json
"""
from __future__ import annotations
import random, json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List


from _util import write_jsonl
from _variants import render_plain, render_formatted, render_mixed
from _obfuscation import obfuscate_text
from pathlib import Path
import json

# Helper to write ground truth per bundle
def _append_ground_truth(gt_dir: Path, row: dict) -> None:
    gt_dir.mkdir(parents=True, exist_ok=True)
    # Write row as usual
    with open(gt_dir / "redact.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "doc_id": row["doc_id"],
            "file_path": row["file_path"],
            "file_type": row["file_type"],
            # "scenario": row["scenario"],  # Removed, no more scenarios
            "pii_spans": row["pii_spans"],
            "decoy_spans": row.get("decoy_spans", [])
        }, ensure_ascii=False) + "\n")
    # Immediately rewrite last line to append _{scenario} to doc_id
    redact_path = gt_dir / "redact.jsonl"
    # Remove scenario logic: doc_id is written as-is, no scenario suffix

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"
DATA_DIR = ROOT / "data"
OUT_ITEMS = DATA_DIR / "items.jsonl"

def load_yaml(path: Path) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_faker(seed: int):
    try:
        import faker
    except Exception:
        import subprocess
        subprocess.run(["pip","install","faker"], check=True)
    from faker import Faker
    fk = Faker("en_US")
    fk.seed_instance(seed)
    random.seed(seed)
    return fk

def synth_person(fk) -> Dict[str, Any]:
    first = fk.first_name()
    last = fk.last_name()
    name = f"{first} {last}"
    # DOB between 1940 and 2005
    start = date(1940,1,1).toordinal()
    end   = date(2005,12,31).toordinal()
    dob = date.fromordinal(random.randint(start, end)).isoformat()
    street = fk.street_address()
    city, state, zipcode = fk.city(), fk.state_abbr(), fk.zipcode()
    address = f"{street}, {city}, {state} {zipcode}"
    email = f"{first.lower()}.{last.lower()}@example.com"
    phone = f"(555) {random.randint(100,999)}-{random.randint(1000,9999)}"
    mrn   = f"MRN-{random.randint(100000,999999)}"
    # SSN-like (not real)
    a,b,c = random.randint(100,999), random.randint(10,99), random.randint(1000,9999)
    ssn   = f"{a}-{b}-{c}"
    return {
        "name": name, "dob": dob, "address": address, "email": email,
        "phone": phone, "mrn": mrn, "ssn": ssn
    }

def base_letter(person: Dict[str, Any]) -> Dict[str, Any]:
    body = " ".join([
        f"Patient: {person['name']}.",
        f"DOB: {person['dob']}.",
        f"Contact: {person['email']}, {person['phone']}.",
        f"Address: {person['address']}.",
        f"Identifiers: {person['mrn']}; SSN-like: {person['ssn']}."
    ])
    text = f"Dear Records Office,\n\n{body}\n\nSincerely,\n{person['name']}\n"
    spans = []
    def mark(t, value):
        start = text.find(value)
        if start >= 0:
            spans.append({"type": t, "start": start, "end": start+len(value)})
    for t in ("NAME","DOB","EMAIL","PHONE","ADDRESS","MRN","SSN"):
        mark(t, person[t.lower()] if t!="NAME" else person["name"])
    meta = {
        "source": "local",
        "seed": random.randint(0,10_000_000),
        "generated_at": datetime.utcnow().isoformat()+"Z",
        **person,
        "body": body
    }
    return {"text": text, "spans": spans, "meta": meta}

def maybe_add_decoy(text: str, p: float, rng: random.Random) -> tuple[str, list[dict]]:
    """Insert a non-PII lookalike and return updated text + decoy span."""
    if rng.random() >= p:
        return text, []
    a,b,c = rng.randint(100,999), rng.randint(10,99), rng.randint(1000,9999)
    marker = f"ORDER #{a}-{b}-{c}"
    inject_point = max(0, len(text)//2 - 5)
    new_text = text[:inject_point] + " " + marker + " " + text[inject_point:]
    start = new_text.find(marker)
    return new_text, [{"label":"DECOY_SSN_PATTERN","start":start,"end":start+len(marker)}]

def make_variants(base: Dict[str, Any], cfg: dict, rng: random.Random, pid: int, bundle_id: str = None, scenario: str = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    variants = cfg["variants"]
    decoy_rate = cfg["non_pii_mix"]["decoy_rate"] if cfg.get("non_pii_mix") else 0.0

    # plain
    if "plain" in variants:
        text = base["text"]
        decoys = []
        if cfg.get("non_pii_mix",{}).get("decoy_patterns", False):
            text, decoys = maybe_add_decoy(text, decoy_rate, rng)
        doc_id = f"{bundle_id}_plain_{scenario}" if bundle_id and scenario else f"loc_{pid}_plain"
        rows.append({
            "doc_id": doc_id,
            "variant": "plain",
            "file_path": "",
            "file_type": "plain",
            "scenario": scenario,
            "bundle_id": bundle_id,
            "text": text,
            "pii_spans": base["spans"],
            "decoy_spans": decoys,
            "blocks_meta": [],
            "meta": {k:v for k,v in base["meta"].items() if k!="body"}
        })

    # formatted
    if "formatted" in variants:
        t = render_formatted(base["meta"])
        decoys = []
        if cfg.get("non_pii_mix",{}).get("decoy_patterns", False):
            t, decoys = maybe_add_decoy(t, decoy_rate, rng)
        doc_id = f"{bundle_id}_formatted_{scenario}" if bundle_id and scenario else f"loc_{pid}_formatted"
        rows.append({
            "doc_id": doc_id,
            "variant": "formatted",
            "file_path": "",
            "file_type": "formatted",
            "scenario": scenario,
            "bundle_id": bundle_id,
            "text": t,
            "pii_spans": base["spans"],
            "decoy_spans": decoys,
            "blocks_meta": ["email_header","kv_fence","table_fields"],
            "meta": {k:v for k,v in base["meta"].items() if k!="body"}
        })

    # obfuscated
    if "obfuscated" in variants:
        t = obfuscate_text(base["text"], rng=rng)
        decoys = []
        if cfg.get("non_pii_mix",{}).get("decoy_patterns", False):
            t, decoys = maybe_add_decoy(t, decoy_rate, rng)
        doc_id = f"{bundle_id}_obfuscated_{scenario}" if bundle_id and scenario else f"loc_{pid}_obfuscated"
        rows.append({
            "doc_id": doc_id,
            "variant": "obfuscated",
            "file_path": "",
            "file_type": "obfuscated",
            "scenario": scenario,
            "bundle_id": bundle_id,
            "text": t,
            "pii_spans": base["spans"],
            "decoy_spans": decoys,
            "blocks_meta": ["obfuscation"],
            "meta": {k:v for k,v in base["meta"].items() if k!="body"}
        })

    # mixed (non-PII heavy)
    if "mixed" in variants:
        mix = render_mixed(base["meta"], rng)
        t = mix["text"]
        decoys = []
        if cfg.get("non_pii_mix",{}).get("decoy_patterns", False):
            t, decoys = maybe_add_decoy(t, decoy_rate, rng)
        doc_id = f"{bundle_id}_mixed_{scenario}" if bundle_id and scenario else f"loc_{pid}_mixed"
        rows.append({
            "doc_id": doc_id,
            "variant": "mixed",
            "file_path": "",
            "file_type": "mixed",
            "scenario": scenario,
            "bundle_id": bundle_id,
            "text": t,
            "pii_spans": base["spans"],
            "decoy_spans": decoys,
            "blocks_meta": mix.get("blocks_meta", []),
            "meta": {k:v for k,v in base["meta"].items() if k!="body"}
        })

    return rows

def main():
    cfg = load_yaml(CONFIGS / "seeding.yaml")
    fk = ensure_faker(seed=int(cfg["limits"]["random_seed"]))
    rng = random.Random(cfg["limits"]["random_seed"])

    n_docs = int(cfg["limits"]["n_documents"])
    items: List[Dict[str, Any]] = []

    # Import all format renderers
    from _formats import (
        render_note, render_csv_labs, render_csv_meds, render_csv_vitals,
        render_hl7, render_fhir, render_cda, render_email, render_ics
    )

    bundle_root = DATA_DIR / "bundles"
    bundle_root.mkdir(parents=True, exist_ok=True)

    formats = cfg.get("formats", [
        "note", "csv_labs", "csv_meds", "csv_vitals", "hl7", "fhir", "cda", "email", "ics"
    ])

    for i in range(n_docs):
        person = synth_person(fk)
        base = base_letter(person)
        bundle_id = f"bundle_{i:04d}"
        bundle_dir = bundle_root / bundle_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        gt_dir = DATA_DIR / "ground_truth" / bundle_id

        meta = dict(base["meta"], bundle_id=bundle_id)
        for file_counter, fmt in enumerate(formats):
            file_seed = int(f"{cfg['limits']['random_seed']}{i:04d}{file_counter:02d}")
            file_rng = random.Random(file_seed)
            if fmt == "note":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_note(meta, bundle_dir, i, file_rng)
            elif fmt == "csv_labs":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_csv_labs(meta, bundle_dir, file_rng)
            elif fmt == "csv_meds":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_csv_meds(meta, bundle_dir, file_rng)
            elif fmt == "csv_vitals":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_csv_vitals(meta, bundle_dir, file_rng)
            elif fmt == "hl7":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_hl7(meta, bundle_dir, file_rng)
            elif fmt == "fhir":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_fhir(meta, bundle_dir, file_rng)
            elif fmt == "cda":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_cda(meta, bundle_dir, file_rng)
            elif fmt == "email":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_email(meta, bundle_dir, file_rng)
            elif fmt == "ics":
                text, file_path, file_type, blocks_meta, pii_spans, decoy_spans = render_ics(meta, bundle_dir, file_rng)
            else:
                continue
            item = {
                "bundle_id": bundle_id,
                "file_path": file_path,
                "file_type": file_type,
                "doc_id": f"{bundle_id}_{fmt}",
                "variant": fmt,
                "text": text,
                "pii_spans": pii_spans,
                "decoy_spans": decoy_spans,
                "blocks_meta": blocks_meta,
                "meta": meta
            }
            items.append(item)
            # Write ground truth for this file
            _append_ground_truth(gt_dir, item)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_ITEMS, items)
    # quick summary
    from collections import Counter
    c = Counter([row["file_type"] for row in items])
    print(f"Wrote {len(items)} rows to {OUT_ITEMS}. File types: {dict(c)} Bundles: {n_docs}")

if __name__ == "__main__":
    main()
