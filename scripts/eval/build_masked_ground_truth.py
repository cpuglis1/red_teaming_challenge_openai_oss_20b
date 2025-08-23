#!/usr/bin/env python3
"""
Backfill masked ground-truth from data/items.jsonl (span -> [REDACTED]).

Usage:
  python scripts/eval/build_masked_ground_truth.py \
      --items data/items.jsonl \
      --out-root data/ground_truth \
      --sidecars

Notes:
- Only PII spans are masked. Decoys are preserved (so you can measure over-redaction).
- Overlapping/adjacent spans are coalesced before masking to avoid index drift.
- We never mutate line endings or encoding; masking is slice-based.
"""
import argparse, json, sys, hashlib
from pathlib import Path
from typing import List, Dict, Any

MASK_TOKEN = "[REDACTED]"

def coalesce_spans(spans: List[Dict[str, int]]) -> List[Dict[str, int]]:
    """Merge overlapping/adjacent [start,end) spans."""
    if not spans:
        return []
    ss = sorted(spans, key=lambda s: (int(s["start"]), int(s["end"])))
    out = [dict(ss[0])]
    for s in ss[1:]:
        last = out[-1]
        if int(s["start"]) <= int(last["end"]):  # overlap or touching
            last["end"] = max(int(last["end"]), int(s["end"]))
        else:
            out.append(dict(s))
    return out

def mask_text(text: str, spans: List[Dict[str, int]], mask: str = MASK_TOKEN) -> str:
    """Replace each [start:end) slice with mask, preserving everything else."""
    if not spans:
        return text
    spans = coalesce_spans(spans)
    parts = []
    cur = 0
    n = len(text)
    for s in spans:
        a = max(0, min(int(s["start"]), n))
        b = max(0, min(int(s["end"]), n))
        if a < cur:
            a = cur  # already covered by previous span merge
        parts.append(text[cur:a])
        parts.append(mask)
        cur = b
    parts.append(text[cur:])
    return "".join(parts)

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/items.jsonl", help="Path to items.jsonl")
    ap.add_argument("--out-root", default="data/ground_truth", help="Output root dir")
    ap.add_argument("--mask-token", default=MASK_TOKEN, help="Mask token to insert")
    ap.add_argument("--sidecars", action="store_true", help="Also write *.redacted.txt files")
    args = ap.parse_args()

    items_path = Path(args.items)
    out_root = Path(args.out_root)
    if not items_path.exists():
        print(f"ERROR: {items_path} not found", file=sys.stderr)
        sys.exit(1)

    by_bundle: Dict[str, List[Dict[str, Any]]] = {}
    with items_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception as e:
                print(f"[warn] JSON parse failed on line {line_num}: {e}", file=sys.stderr)
                continue
            bundle = row.get("bundle_id") or "bundle_unknown"
            by_bundle.setdefault(bundle, []).append(row)

    total = 0
    for bundle, rows in by_bundle.items():
        gt_dir = out_root / bundle
        gt_dir.mkdir(parents=True, exist_ok=True)
        out_file = gt_dir / "redact.jsonl"
        with out_file.open("w", encoding="utf-8") as out:
            for row in rows:
                text = row.get("text", "")
                pii_spans = row.get("pii_spans", [])
                decoy_spans = row.get("decoy_spans", [])
                masked = mask_text(text, pii_spans, mask=args.mask_token)
                payload = {
                    "bundle_id": row.get("bundle_id"),
                    "doc_id": row.get("doc_id"),
                    "file_path": row.get("file_path"),
                    "file_type": row.get("file_type"),
                    "variant": row.get("variant"),
                    "mask_token": args.mask_token,
                    "doc_hash": sha256_str(text),
                    "pii_spans": pii_spans,
                    "decoy_spans": decoy_spans,
                    "expected_redacted": masked
                }
                out.write(json.dumps(payload, ensure_ascii=False) + "\n")
                total += 1

                if args.sidecars:
                    side_dir = gt_dir / "redacted_files"
                    side_dir.mkdir(parents=True, exist_ok=True)
                    # Stable filename: prefer the original filename if present
                    name = Path(row.get("file_path") or f"{row.get('doc_id','doc')}.txt").name
                    with (side_dir / f"{name}.redacted.txt").open("w", encoding="utf-8") as rf:
                        rf.write(masked)

    print(f"Wrote {total} gold rows → {out_root}/<bundle>/redact.jsonl")
    if args.sidecars:
        print("Sidecar masked files written under redacted_files/ per bundle.")

if __name__ == "__main__":
    main()