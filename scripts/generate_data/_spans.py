# scripts/_spans.py
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
from typing import List, Dict, Tuple

def _find_all(text: str, needle: str) -> List[Tuple[int,int]]:
    if not needle:
        return []
    out, start = [], 0
    while True:
        i = text.find(needle, start)
        if i == -1:
            break
        out.append((i, i+len(needle)))
        start = i + len(needle)
    return out

def spans_literal(text: str, value: str, typ: str) -> List[Dict]:
    return [{"type": typ, "start": s, "end": e} for (s,e) in _find_all(text, value)]

def span_decoy(text: str, marker: str, label: str = "DECOY_SSN_PATTERN") -> List[Dict]:
    return [{"label": label, "start": s, "end": e} for (s,e) in _find_all(text, marker)]

# ----------------------
# Format-specific helpers
# ----------------------

def hl7_name_spans(text: str, full_name: str) -> List[Dict]:
    # HL7 PID-5 is Family^Given
    parts = full_name.split()
    if len(parts) < 2:
        return []
    given = parts[0]
    family = parts[-1]
    out = []
    for (s,e) in _find_all(text, family):
        out.append({"type":"NAME","start":s,"end":e})
    for (s,e) in _find_all(text, given):
        out.append({"type":"NAME","start":s,"end":e})
    return out

def hl7_dob_spans(text: str, dob_iso: str) -> List[Dict]:
    ymd = dob_iso.replace("-", "")
    return [{"type":"DOB","start": s, "end": e} for (s,e) in _find_all(text, ymd)]

def hl7_address_spans(text: str, street: str, apt: str, city: str, state: str, postal: str, country: str) -> List[Dict]:
    vals = [v for v in [street, apt, city, state, postal, country] if v]
    out = []
    for v in vals:
        for (s,e) in _find_all(text, v):
            out.append({"type":"ADDRESS","start": s, "end": e})
    return out

def hl7_phone_spans(text: str, phone_digits: str) -> List[Dict]:
    # We render as ^area^rest in PID-13; extract those tokens
    if len(phone_digits) < 7:  # safety
        return []
    area = phone_digits[:3]
    rest = phone_digits[3:]
    out = []
    for (s,e) in _find_all(text, area):
        out.append({"type":"PHONE","start":s,"end":e})
    for (s,e) in _find_all(text, rest):
        out.append({"type":"PHONE","start":s,"end":e})
    return out

def cda_phone_spans(text: str, phone_digits: str) -> List[Dict]:
    normalized = "+1" + phone_digits
    return [{"type":"PHONE","start": s, "end": e} for (s,e) in _find_all(text, normalized)]

def fhir_name_spans(text: str, given: str, family: str) -> List[Dict]:
    out = []
    for (s,e) in _find_all(text, family):
        out.append({"type":"NAME","start":s,"end":e})
    for (s,e) in _find_all(text, given):
        out.append({"type":"NAME","start":s,"end":e})
    return out

def address_component_spans(text: str, line: str, city: str, state: str, postal: str) -> List[Dict]:

    vals = [v for v in [line, city, state, postal] if v]
    out = []
    for v in vals:
        for (s,e) in _find_all(text, v):
            out.append({"type":"ADDRESS","start": s, "end": e})
    return out

# CSV format: extract spans for each cell value
def csv_spans(row: dict, text: str) -> List[Dict]:
    out = []
    for k, v in row.items():
        if v:
            for (s,e) in _find_all(text, v):
                out.append({"type":k.upper(), "start":s, "end":e})
    return out

# FHIR format: email, phone
def fhir_email_spans(text: str, email: str) -> List[Dict]:
    return [{"type":"EMAIL","start": s, "end": e} for (s,e) in _find_all(text, email)]

def fhir_phone_spans(text: str, phone: str) -> List[Dict]:
    return [{"type":"PHONE","start": s, "end": e} for (s,e) in _find_all(text, phone)]

# CDA format: name
def cda_name_spans(text: str, name: str) -> List[Dict]:
    return [{"type":"NAME","start": s, "end": e} for (s,e) in _find_all(text, name)]

# Email format: extract spans for email address, name, etc.
def email_spans(text: str, email: str, name: str) -> List[Dict]:
    out = []
    for (s,e) in _find_all(text, email):
        out.append({"type":"EMAIL","start": s, "end": e})
    for (s,e) in _find_all(text, name):
        out.append({"type":"NAME","start": s, "end": e})
    return out

# ICS format: extract spans for name, email, location
def ics_spans(text: str, name: str, email: str, location: str) -> List[Dict]:
    out = []
    for (s,e) in _find_all(text, name):
        out.append({"type":"NAME","start": s, "end": e})
    for (s,e) in _find_all(text, email):
        out.append({"type":"EMAIL","start": s, "end": e})
    for (s,e) in _find_all(text, location):
        out.append({"type":"LOCATION","start": s, "end": e})
    return out
