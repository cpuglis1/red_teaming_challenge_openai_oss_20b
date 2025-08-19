#!/usr/bin/env python3
"""
# Replay-only scoring (no network)
python scripts/run/runner_replay.py --responses outputs/responses/template_vs_ui.jsonl --print-table
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "eval"))
import score_responses

def main():
    parser = argparse.ArgumentParser(description="Replay scoring of responses (no network)")
    parser.add_argument("--responses", required=True, help="Path to responses JSONL")
    parser.add_argument("--print-table", action="store_true", help="Print summary table")
    parser.add_argument("--out", help="Output summary path")
    args = parser.parse_args()
    score_responses.main()

if __name__ == "__main__":
    main()
