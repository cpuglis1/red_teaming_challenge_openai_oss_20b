#!/usr/bin/env python3
"""
# Build prompts (no network)
python scripts/prompts/build_prompts_metadata_only.py --limit 20
"""
import argparse
import hashlib
import json
from pathlib import Path
import itertools
import sys
import os

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
from prompt_builders import build_control, build_metadata_only

def main():
    parser = argparse.ArgumentParser(description="Build metadata_only prompts as JSONL.")
    parser.add_argument("--bundle-glob", default="data/bundles/bundle_*/**/*", help="Glob for input files")
    parser.add_argument("--file-types", default="note,hl7,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals", help="Comma-separated file types")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of docs")
    parser.add_argument("--out", default="outputs/requests/metadata_only/requests.jsonl", help="Output JSONL path")
    args = parser.parse_args()

    file_types = set(args.file_types.split(","))
    files = sorted(Path().glob(args.bundle_glob))
    files = [f for f in files if f.is_file() and (f.suffix[1:] in file_types or f.suffix == "")]
    if args.limit:
        files = files[:args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    with out_path.open("w", encoding="utf-8") as out:
        for file in files:
            try:
                doc_text = file.read_text(encoding="utf-8")
            except Exception:
                continue
            doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()
            doc_id = file.stem
            file_type = file.suffix[1:] if file.suffix else None
            scenarios = ["control", "meta_exam", "meta_live"]
            for scenario in scenarios:
                if scenario == "control":
                    messages = build_control(doc_text)
                else:
                    messages = build_metadata_only(doc_text, scenario)
                line = {
                    "doc_id": doc_id,
                    "file_path": str(file),
                    "file_type": file_type,
                    "scenario": scenario,
                    "doc_hash": doc_hash,
                    "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                    "messages": messages
                }
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
                n_written += 1
    print(f"Wrote {n_written} lines → {out_path}")

if __name__ == "__main__":
    main()
