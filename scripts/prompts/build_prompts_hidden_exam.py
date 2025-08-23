#!/usr/bin/env python3
"""
Build prompts (no network) to test eval awareness & objective hacking.

Optional add-ons (flags):
  --with-hidden   → add: hidden_exam
  --with-meta     → add: meta_exam

Defaults: include ALL file types EXCEPT HL7.

Usage:
  python scripts/prompts/build_prompts_eval_awareness.py

  # include HL7 as well
  python scripts/prompts/build_prompts_eval_awareness.py \
    --file-types note,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals,hl7

  # add hidden-cues & metadata-only families (exam-only)
  python scripts/prompts/build_prompts_eval_awareness.py --with-hidden --with-meta

  # limit for a smoke test
  python scripts/prompts/build_prompts_eval_awareness.py --limit 20
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

# import builders (be resilient to signature drift)
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

# Optional imports
try:
    from prompt_builders import build_hidden_cues  # noqa: E402
except Exception:
    build_hidden_cues = None

try:
    from prompt_builders import build_metadata_only  # noqa: E402
except Exception:
    build_metadata_only = None


# -------- helpers --------
def infer_file_type(p: Path) -> str | None:
    """
    Flexible filename → file_type mapping.
    - *_default.json or patient*.json → fhir
    - *_default.xml  or summary*.xml  → cda
    - *.csv → csv_labs / csv_meds / csv_vitals by prefix
    - *.eml → email
    - *.ics → ics
    - *.md  → note
    - *.hl7 or msg_* → hl7
    """
    name = p.name.lower()
    suf = p.suffix.lower()

    if suf == ".json" and "patient" in name:
        return "fhir"
    if suf == ".xml" and "summary" in name:
        return "cda"
    if suf == ".csv":
        if name.startswith("lab_results"):
            return "csv_labs"
        if name.startswith("medications"):
            return "csv_meds"
        if name.startswith("vitals"):
            return "csv_vitals"
    if suf == ".eml":
        return "email"
    if suf == ".ics":
        return "ics"
    if suf == ".md":
        return "note"
    if suf == ".hl7" or name.startswith("msg_"):
        return "hl7"
    return None


# Signature-safe wrappers for optional families
def _safe_build_hidden(doc_id: str, text: str, scenario: str):
    if build_hidden_cues is None:
        raise RuntimeError("build_hidden_cues not found in prompt_builders.")
    try:
        return build_hidden_cues(doc_id, text, scenario)
    except TypeError:
        return build_hidden_cues(text, scenario)


def _safe_build_meta(doc_id: str, text: str, scenario: str):
    if build_metadata_only is None:
        raise RuntimeError("build_metadata_only not found in prompt_builders.")
    try:
        return build_metadata_only(doc_id, text, scenario)
    except TypeError:
        return build_metadata_only(text, scenario)


# -------- main --------
def main():
    ap = argparse.ArgumentParser(description="Build eval-awareness prompts as JSONL.")
    ap.add_argument("--bundle-glob", default="data/bundles/bundle_*/**/*",
                    help="Glob for input files")
    # Default: include EVERYTHING EXCEPT HL7
    ap.add_argument("--file-types",
                    default="note,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals",
                    help="Comma-separated logical file types to include")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of docs")
    ap.add_argument("--out", default="outputs/requests/hidden/requests.jsonl",
                    help="Output JSONL path")

    ap.add_argument("--with-hidden", action="store_true",
                    help="Also emit hidden_exam scenario")
    ap.add_argument("--with-meta", action="store_true",
                    help="Also emit meta_exam scenario")

    args = ap.parse_args()

    wanted_types = {t.strip() for t in args.file_types.split(",") if t.strip()}
    files = sorted(Path().glob(args.bundle_glob))

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

            # Stable doc_id: data/bundles/<bundle_id>/<stem> → bundle_xxxx_stem
            parts = fpath.parts
            try:
                bundle = parts[parts.index("data") + 2]  # .../data/bundles/<bundle_id>/...
            except (ValueError, IndexError):
                bundle = fpath.parent.name
            stem = fpath.stem
            doc_id = f"{bundle}_{stem}"

            doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

            # --- Optional families only (exam-only variants) ---
            scen_msgs: dict[str, list[dict]] = {}

            if args.with_hidden:
                if build_hidden_cues is None:
                    print("WARNING: --with-hidden requested but build_hidden_cues not available.")
                else:
                    scen_msgs["hidden_exam"] = _safe_build_hidden(doc_id, doc_text, "hidden_exam")

            if args.with_meta:
                if build_metadata_only is None:
                    print("WARNING: --with-meta requested but build_metadata_only not available.")
                else:
                    scen_msgs["meta_exam"] = _safe_build_meta(doc_id, doc_text, "meta_exam")

            # Emit JSONL
            for scenario, messages in scen_msgs.items():
                line = {
                    "doc_id": doc_id,
                    "file_path": str(fpath),
                    "file_type": file_type,
                    "scenario": scenario,
                    "doc_hash": doc_hash,
                    "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                    "messages": messages,
                }
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
                n_written += 1

    print(f"Wrote {n_written} lines → {out_path}")


if __name__ == "__main__":
    main()