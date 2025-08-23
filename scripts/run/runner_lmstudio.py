#!/usr/bin/env python3
"""
# Run against LM Studio local server
python scripts/run/runner_lmstudio.py --base-url http://localhost:1234/v1 \
  --model gpt-oss-20b \
  --requests outputs/requests/template_vs_ui/requests.jsonl \
  --out outputs/responses/template_vs_ui.jsonl
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from datetime import datetime

def post_request(url, payload, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)

def main():
    parser = argparse.ArgumentParser(description="Run prompts against LM Studio local server.")
    parser.add_argument("--base-url", default="http://localhost:1234/v1", help="Base URL for LM Studio API")
    parser.add_argument("--requests", required=True, help="Path to requests JSONL")
    parser.add_argument("--out", help="Output JSONL path")
    parser.add_argument("--model", default=os.environ.get("LMSTUDIO_MODEL", "gpt-oss-20b"), help="Model name")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout (seconds)")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per request")
    parser.add_argument("--sleep", type=float, default=0.5, help="Sleep between retries (seconds)")
    args = parser.parse_args()

    req_path = Path(args.requests)
    family = req_path.parent.parent.name if req_path.parent.parent.name in {"template_vs_ui","metadata_only","hidden_cues"} else None
    out_path = Path(args.out) if args.out else (
        Path(f"outputs/responses/{family}/responses.jsonl") if family else Path("outputs/responses/responses.jsonl")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_written = 0
    with req_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            req = json.loads(line)
            payload = {
                "model": args.model,
                "messages": req["messages"],
                "temperature": req["gen"]["temperature"],
                "top_p": req["gen"]["top_p"],
                "max_tokens": req["gen"]["max_tokens"],
                "n": req["gen"].get("n", 1)
            }
            if "seed" in req:
                payload["seed"] = req["seed"]
            response_obj = None
            for attempt in range(args.retries):
                try:
                    resp = post_request(args.base_url + "/chat/completions", payload, args.timeout)
                    choice = resp["choices"][0]["message"]
                    usage = resp.get("usage", {})
                    response_obj = {
                        "text": choice.get("content", ""),
                        "reasoning": choice.get("reasoning", ""),
                        "finish_reason": resp["choices"][0].get("finish_reason"),
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0)
                        }
                    }
                    break
                except Exception as e:
                    time.sleep(args.sleep * (2 ** attempt))
                    last_error = str(e)
            if response_obj is None:
                response_obj = {
                    "text": "",
                    "finish_reason": None,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "error": last_error
                }
            out_line = {
                "doc_id": req["doc_id"],
                "file_path": req["file_path"],
                "file_type": req["file_type"],
                "scenario": req["scenario"],
                "doc_hash": req["doc_hash"],
                "response": response_obj,
                "run_meta": {
                    "base_url": args.base_url,
                    "model": args.model,
                    "ts": datetime.now().isoformat(),
                    "timeout": args.timeout,
                    "retries": args.retries
                }
            }
            fout.write(json.dumps(out_line, ensure_ascii=False) + "\n")
            n_written += 1
    print(f"Wrote {n_written} lines → {out_path}")

if __name__ == "__main__":
    main()
