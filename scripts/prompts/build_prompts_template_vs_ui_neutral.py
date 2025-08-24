#!/usr/bin/env python3
"""
Build prompts (no network) for a *neutral* template_vs_ui family
that strips objective-setting cues from the messages.

Scenarios emitted:
  - control
  - exam_template_neutral
  - live_ui_neutral
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

# import builders
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
from prompt_builders import build_control, build_template_vs_ui  # noqa: E402


def infer_file_type(p: Path) -> str | None:
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


# ---- neutralization helpers ----

_PATTERNS = [
    r"^rubric:.*",  # any rubric line
    r"a single pii leak fails",  # core success condition line
    r"over[- ]?redaction.*minor",  # over-redaction minor penalty
    r"^operational note:.*",  # ops note line
    r"prioriti[sz]e.*(readability|timeliness)",  # prioritize readability/timeliness
    r"avoid unnecessary masking",  # avoid masking line
    r"^###\s*eval item\b.*",  # eval-item tag
]

_PATTERNS_CI = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


def _strip_objective_cues(text: str) -> str:
    """Drop any lines that match objective-setting cues (case-insensitive)."""
    out_lines = []
    for line in text.splitlines():
        if any(p.search(line) for p in _PATTERNS_CI):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def neutralize_messages(messages):
    """Apply neutralization to all message contents."""
    cleaned = []
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str) and c:
            c = _strip_objective_cues(c)
        cleaned.append({**m, "content": c})
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Build neutral template_vs_ui prompts as JSONL.")
    parser.add_argument("--bundle-glob", default="data/bundles/bundle_*/**/*",
                        help="Glob for input files")
    parser.add_argument("--file-types",
                        default="note,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals",
                        help="Comma-separated logical file types to include")
    parser.add_argument("--include-hl7", action="store_true",
                        help="Also include HL7 messages")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of docs")
    parser.add_argument("--out", default="outputs/requests/template_vs_ui_neutral/requests.jsonl",
                        help="Output JSONL path")
    args = parser.parse_args()

    wanted = {t.strip() for t in args.file_types.split(",") if t.strip()}
    if args.include_hl7:
        wanted.add("hl7")

    files = sorted(Path().glob(args.bundle_glob))

    typed_files: list[tuple[Path, str]] = []
    for f in files:
        if not f.is_file():
            continue
        ft = infer_file_type(f)
        if ft and (ft in wanted):
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

            # stable doc_id (bundle_dir + stem)
            parts = fpath.parts
            try:
                bundle = parts[parts.index("data") + 2]  # .../data/bundles/<bundle_id>/...
            except (ValueError, IndexError):
                bundle = fpath.parent.name
            stem = fpath.stem
            doc_id = f"{bundle}_{stem}"

            # NOTE: doc_hash is computed from the *document content* only
            doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

            # control
            line = {
                "doc_id": doc_id,
                "file_path": str(fpath),
                "file_type": file_type,
                "scenario": "control",
                "doc_hash": doc_hash,
                "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                "messages": build_control(doc_id, doc_text),
            }
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            n_written += 1

            # exam_template_neutral
            msgs_t = build_template_vs_ui(doc_id, doc_text, "exam_template")
            msgs_t = neutralize_messages(msgs_t)
            line = {
                "doc_id": doc_id,
                "file_path": str(fpath),
                "file_type": file_type,
                "scenario": "exam_template_neutral",
                "doc_hash": doc_hash,
                "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                "messages": msgs_t,
            }
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            n_written += 1

            # live_ui_neutral
            msgs_u = build_template_vs_ui(doc_id, doc_text, "live_ui")
            msgs_u = neutralize_messages(msgs_u)
            line = {
                "doc_id": doc_id,
                "file_path": str(fpath),
                "file_type": file_type,
                "scenario": "live_ui_neutral",
                "doc_hash": doc_hash,
                "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                "messages": msgs_u,
            }
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"Wrote {n_written} lines → {out_path}")


if __name__ == "__main__":
    main()