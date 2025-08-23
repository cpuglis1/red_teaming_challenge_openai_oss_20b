#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))
from prompt_builders import build_control, build_template_vs_ui_explicit

def infer_file_type(p: Path) -> str | None:
    n, suf = p.name.lower(), p.suffix.lower()
    if suf == ".json" and "patient" in n: return "fhir"
    if suf == ".xml"  and "summary" in n: return "cda"
    if suf == ".csv":
        if n.startswith("lab_results"): return "csv_labs"
        if n.startswith("medications"): return "csv_meds"
        if n.startswith("vitals"): return "csv_vitals"
    if suf == ".eml": return "email"
    if suf == ".ics": return "ics"
    if suf == ".md":  return "note"
    if suf == ".hl7" or n.startswith("msg_"): return "hl7"
    return None

def main():
    ap = argparse.ArgumentParser(description="Build template_vs_ui *explicit* prompts (neutral objectives).")
    ap.add_argument("--bundle-glob", default="data/bundles/bundle_*/**/*")
    ap.add_argument("--file-types",  default="note,fhir,cda,email,ics,csv_labs,csv_meds,csv_vitals")
    ap.add_argument("--include-hl7", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="outputs/requests/template_vs_ui_explicit/requests.jsonl")
    args = ap.parse_args()

    wanted = {t.strip() for t in args.file_types.split(",") if t.strip()}
    if args.include_hl7:
        wanted.add("hl7")

    files = sorted(Path().glob(args.bundle_glob))
    typed = [(f, infer_file_type(f)) for f in files if f.is_file()]
    typed = [(f, ft) for (f, ft) in typed if ft and ft in wanted]
    if args.limit:
        typed = typed[:args.limit]

    outp = Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with outp.open("w", encoding="utf-8") as out:
        for fpath, file_type in typed:
            try:
                doc_text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            parts = fpath.parts
            try:
                bundle = parts[parts.index("data")+2]
            except (ValueError, IndexError):
                bundle = fpath.parent.name
            stem = fpath.stem
            doc_id = f"{bundle}_{stem}"
            doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

            # control
            out.write(json.dumps({
                "doc_id": doc_id, "file_path": str(fpath), "file_type": file_type,
                "scenario": "control", "doc_hash": doc_hash,
                "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                "messages": build_control(doc_id, doc_text)
            }, ensure_ascii=False) + "\n"); n += 1

            # exam (explicit framing, no score incentives)
            out.write(json.dumps({
                "doc_id": doc_id, "file_path": str(fpath), "file_type": file_type,
                "scenario": "exam_template_explicit", "doc_hash": doc_hash,
                "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                "messages": build_template_vs_ui_explicit(doc_id, doc_text, "exam_template_explicit")
            }, ensure_ascii=False) + "\n"); n += 1

            # live (explicit framing, no score incentives)
            out.write(json.dumps({
                "doc_id": doc_id, "file_path": str(fpath), "file_type": file_type,
                "scenario": "live_ui_explicit", "doc_hash": doc_hash,
                "gen": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "n": 1},
                "messages": build_template_vs_ui_explicit(doc_id, doc_text, "live_ui_explicit")
            }, ensure_ascii=False) + "\n"); n += 1

    print(f"Wrote {n} lines → {outp}")

if __name__ == "__main__":
    main()