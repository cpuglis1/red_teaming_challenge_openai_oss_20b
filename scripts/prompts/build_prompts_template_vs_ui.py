#!/usr/bin/env python3
"""
Build prompts (no network) for the template_vs_ui family.

Usage:
  # all but HL7 (default)
  python scripts/prompts/build_prompts_template_vs_ui.py

  # include HL7 as well
  python scripts/prompts/build_prompts_template_vs_ui.py --file-types note,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals,hl7

  # limit for smoke test
  python scripts/prompts/build_prompts_template_vs_ui.py --limit 20
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

# import builders
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
from prompt_builders import build_control, build_template_vs_ui  # noqa: E402


# Map filenames to logical file_type used elsewhere in the pipeline
def infer_file_type(p: Path) -> str | None:
    """
    Be flexible about dataset filenames:
    - patient_default.json (or patient.json)  -> fhir
    - summary_default.xml (or summary.xml)    -> cda
    - msg_001_default.hl7 (any *.hl7)         -> hl7
    - lab_results_default.csv (or lab_results.csv) -> csv_labs
    - medications_default.csv (or medications.csv) -> csv_meds
    - vitals_default.csv (or vitals.csv)           -> csv_vitals
    - thread_001.eml (any *.eml)               -> email
    - followup_default.ics (any *.ics)         -> ics
    - note_03.md (any *.md)                    -> note
    """
    name = p.name.lower()
    suf = p.suffix.lower()

    # Structured docs
    if suf == ".json" and "patient" in name:
        return "fhir"
    if suf == ".xml" and "summary" in name:
        return "cda"

    # Flat files
    if suf == ".csv":
        if name.startswith("lab_results"):
            return "csv_labs"
        if name.startswith("medications"):
            return "csv_meds"
        if name.startswith("vitals"):
            return "csv_vitals"

    # Messages / calendar
    if suf == ".eml":
        return "email"
    if suf == ".ics":
        return "ics"

    # Notes
    if suf == ".md":
        return "note"

    # HL7
    if suf == ".hl7" or name.startswith("msg_"):
        return "hl7"

    # unknown/ignore
    return None


def main():
    parser = argparse.ArgumentParser(description="Build template_vs_ui prompts as JSONL.")
    parser.add_argument(
        "--bundle-glob",
        default="data/bundles/bundle_*/**/*",
        help="Glob for input files",
    )
    # Default: include EVERYTHING EXCEPT HL7
    parser.add_argument(
        "--file-types",
        default="note,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals",
        help="Comma-separated logical file types to include",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of docs")
    parser.add_argument(
        "--out",
        default="outputs/requests/template_vs_ui/requests.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args()

    wanted_types = {t.strip() for t in args.file_types.split(",") if t.strip()}
    files = sorted(Path().glob(args.bundle_glob))

    # keep only files we can type
    typed_files: list[tuple[Path, str]] = []
    for f in files:
        if not f.is_file():
            continue
        ft = infer_file_type(f)
        if ft and (ft in wanted_types):
            typed_files.append((f, ft))

    if args.limit:
        typed_files = typed_files[: args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_written = 0
    with out_path.open("w", encoding="utf-8") as out:
        for fpath, file_type in typed_files:
            try:
                doc_text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            # Stable doc_id: bundle_dir + filename stem
            # e.g., data/bundles/bundle_0003/note_03.md → bundle_0003_note_03
            parts = fpath.parts
            try:
                # .../data/bundles/<bundle_id>/...
                bundle_idx = parts.index("data") + 2
                bundle = parts[bundle_idx]
            except (ValueError, IndexError):
                bundle = fpath.parent.name
            stem = fpath.stem
            doc_id = f"{bundle}_{stem}"

            doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

            for scenario in ("control", "exam_template", "live_ui"):
                if scenario == "control":
                    messages = build_control(doc_id, doc_text)
                else:
                    messages = build_template_vs_ui(doc_id, doc_text, scenario)

                line = {
                    "doc_id": doc_id,
                    "file_path": str(fpath),
                    "file_type": file_type,
                    "scenario": scenario,
                    "doc_hash": doc_hash,
                    "gen": {
                        "temperature": 0.0,
                        "top_p": 1.0,
                        "max_tokens": 2048,
                        "n": 1,
                    },
                    "messages": messages,
                }
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
                n_written += 1

    print(f"Wrote {n_written} lines → {out_path}")


if __name__ == "__main__":
    main()