'''
RUN=merged_$(date -u +%Y%m%dT%H%M%SZ)

python scripts/eval/merge_and_filter_responses.py \
  --inputs \
    outputs/responses/base/template_vs_ui.jsonl \
    outputs/responses/eval_awareness_*/secondary_contrasts.jsonl \
    outputs/responses/payload_cues_*/payload_cues.jsonl \
  --drop-scenarios control \
  --dedupe-key doc_hash+scenario \
  --prefer first \
  --out outputs/responses/$RUN/merged.jsonl

python scripts/eval/score_responses.py \
  --responses outputs/responses/$RUN/merged.jsonl \
  --gt-root data/ground_truth \
  --items data/items.jsonl \
  --out-csv outputs/eval/${RUN}.csv

python scripts/eval/quick_validate.py --csv outputs/eval/${RUN}.csv
'''


#!/usr/bin/env python3
import argparse, json
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True,
                    help="One or more responses*.jsonl files")
    ap.add_argument("--out", required=True,
                    help="Merged, deduped JSONL output path")
    ap.add_argument("--drop-scenarios", default="",
                    help="Comma-separated scenario names to exclude entirely (e.g., 'control')")
    ap.add_argument("--dedupe-key", default="doc_hash+scenario",
                    choices=["doc_hash+scenario","doc_id+scenario"],
                    help="Key used to remove duplicates")
    ap.add_argument("--prefer", default="first", choices=["first","last"],
                    help="If duplicates appear, keep the first seen (default) or last seen")
    args = ap.parse_args()

    drop = {s.strip() for s in args.drop_scenarios.split(",") if s.strip()}

    def mk_key(rec):
        if args.dedupe_key == "doc_hash+scenario":
            return (rec.get("doc_hash"), rec.get("scenario"))
        else:
            return (rec.get("doc_id"), rec.get("scenario"))

    out_rows, seen = [], set()
    for p in args.inputs:
        with Path(p).open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("scenario") in drop:
                    continue
                k = mk_key(rec)
                if args.prefer == "first":
                    if k in seen:
                        continue
                    seen.add(k)
                    out_rows.append(rec)
                else:  # prefer last
                    # remove earlier copy if present
                    if k in seen:
                        for i in range(len(out_rows)-1, -1, -1):
                            if mk_key(out_rows[i]) == k:
                                out_rows.pop(i)
                                break
                    seen.add(k)
                    out_rows.append(rec)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8") as out:
        for r in out_rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(out_rows)} lines → {args.out}")

if __name__ == "__main__":
    main()