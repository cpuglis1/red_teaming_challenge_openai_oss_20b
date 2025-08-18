"""
src/data_generation/non_pii_mixins.py
SPDX-License-Identifier: Apache-2.0

Helper utilities for generating non-PII structured and unstructured data.
"""
import random

def generate_non_pii_tabular(seed=42):
    """Generate tabular non-PII data: vitals, labs, device measurements."""
    rng = random.Random(seed)
    vitals = [
        {"Vital": "BP", "Value": f"{rng.randint(110,140)}/{rng.randint(70,90)} mmHg"},
        {"Vital": "HR", "Value": f"{rng.randint(60,100)} bpm"},
        {"Vital": "Temp", "Value": f"{round(rng.uniform(97.0, 99.5),1)} F"}
    ]
    labs = [
        {"Test": "WBC", "Value": round(rng.uniform(4.0, 11.0),1), "Unit": "10^3/uL"},
        {"Test": "Hgb", "Value": round(rng.uniform(12.0, 16.0),1), "Unit": "g/dL"}
    ]
    devices = [
        {"Device": "Pulse Oximeter", "Value": f"{rng.randint(95,100)}%"}
    ]
    return {"vitals": vitals, "labs": labs, "devices": devices}

def generate_non_pii_unstructured(seed=42):
    """Generate unstructured non-PII text: doctor's notes without identifiers."""
    rng = random.Random(seed)
    notes = [
        "Patient reports feeling well. No complaints.",
        "Physical exam unremarkable. Continue current medications.",
        "Follow-up in 3 months recommended."
    ]
    return rng.choice(notes)

def generate_other_structures(seed=42):
    """Generate other structures: billing codes, encounter summaries."""
    rng = random.Random(seed)
    billing_codes = [
        {"Code": "99213", "Description": "Office/outpatient visit"},
        {"Code": "80053", "Description": "Comprehensive metabolic panel"}
    ]
    encounter_summary = {
        "Summary": "Routine follow-up. Labs within normal limits."
    }
    return {"billing_codes": billing_codes, "encounter_summary": encounter_summary}
