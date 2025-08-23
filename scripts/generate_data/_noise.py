# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
from typing import List
import random, textwrap

CC_SYNS = ["Chief Complaint", "CC", "Reason for Visit", "Presenting Concern"]
HPI_LEADS = [
  "Patient reports", "Pt states", "Patient describes", "Patient notes", "Pt reports"
]
AP_SYNS = ["Assessment/Plan", "Plan", "Assessment & Plan", "A/P"]

FILLER_SENTENCES = [
  "Patient denies new allergies.", "No recent hospitalizations reported.",
  "Family history reviewed and noncontributory.", "Counseled on diet and exercise.",
  "Patient verbalizes understanding.", "Questions answered to satisfaction.",
  "Records reviewed; no outside scans available.", "Follow-up scheduled as discussed.",
  "Time spent in counseling documented.", "Med reconciliation completed."
]

BULLETS = [
  "- Discuss medication adherence.",
  "- Provide written instructions.",
  "- Review home monitoring logs.",
  "- Schedule follow-up labs.",
  "- Consider referral if symptoms persist."
]

def pick(rng, seq): return rng.choice(seq)
def some(rng, seq, kmin=1, kmax=3): return rng.sample(seq, k=rng.randint(kmin, min(kmax, len(seq))))

def jitter_whitespace(rng, text: str) -> str:
    # randomly insert extra blank lines or trailing spaces (no zero-width chars here)
    lines = text.split("\n")
    out = []
    for L in lines:
        out.append(L + (" " * rng.randint(0,1)))
        if rng.random() < 0.15: out.append("")  # occasional blank line
    return "\n".join(out)

def hyphenate_randomly(rng, text: str, p=0.1) -> str:
    # randomly break a few long words across lines with hyphen
    words = text.split(" ")
    for i,w in enumerate(words):
        if len(w) > 10 and rng.random() < p:
            cut = rng.randint(4, min(8, len(w)-3))
            words[i] = w[:cut] + "-\n" + w[cut:]
    return " ".join(words)

def mk_paragraph(rng, lead: str, body: str) -> str:
    return f"**{lead}:** " + body

def mk_bullets(rng) -> str:
    return "\n".join(some(rng, BULLETS, 2, 4))
