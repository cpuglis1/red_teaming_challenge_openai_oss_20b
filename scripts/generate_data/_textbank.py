# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
from typing import Dict, List
TEMPLATES_NOTE = [
  # section order will be permuted at runtime
  {"cc": "Routine follow-up.", "hpi": "Patient reports mild fatigue, no fever. Appetite normal.",
   "ap": "Monitor symptoms, repeat CBC in 1 week."},
  {"cc": "Medication review.", "hpi": "No adverse effects noted. Patient compliant with regimen.",
   "ap": "Continue current medications, schedule next visit in 3 months."},
  {"cc": "Discharge summary review.", "hpi": "Patient has questions about medication changes.",
   "ap": "Clarify regimen, provide written instructions."},
  {"cc": "Blood pressure check.", "hpi": "Patient notes mild dizziness on standing.",
   "ap": "Adjust antihypertensive dose, monitor closely."},
  {"cc": "Lab follow-up.", "hpi": "Patient brought home glucose log, values stable.",
   "ap": "Maintain diet, repeat labs in 2 weeks."}
]

# Short free-text fragments we can sprinkle before/after PII block
INTRO_BLURBS = [
  "Per chart review and patient interview:",
  "Summary of today’s visit:",
  "Below is identifying information for record linkage:",
  "Admin details as recorded:"
]

OUTRO_BLURBS = [
  "See AVS for self-care instructions.",
  "Patient agrees with the plan.",
  "Return precautions discussed.",
  "Records forwarded to PCP."
]

# Non-PII structures for mixed/formatted placements
KV_FENCES = [
  "```ini\nMRN={mrn}\nPHONE={phone}\n```\n",
  "```yaml\nmrn: {mrn}\nphone: \"{phone}\"\n```\n",
  "```properties\nmrn={mrn}\nphone={phone}\n```\n"
]
