# scripts/_variants.py
# SPDX-License-Identifier: Apache-2.0
from typing import Tuple, Dict, Any

MASK = "[REDACT]"
def render_mixed(note_meta: Dict[str, Any], rng) -> Dict[str, Any]:
    """Stub: Compose a realistic document with multiple non-PII structures."""
    blocks_meta = ["soap", "labs_table", "meds_table", "vitals_table", "kv_fence", "fhir_json", "hl7", "email_header"]
    text = f"Mixed variant for {note_meta.get('name', 'John Doe')}\n" + note_meta.get("body", "")
    return {"text": text, "blocks_meta": blocks_meta}

def render_plain(note: str) -> str:
    return note

def render_formatted(note_meta: Dict[str, Any]) -> str:
    # render some fields as a markdown table + email header + code block
    name = note_meta.get("name", "John Doe")
    email = note_meta.get("email", "john@example.com")
    phone = note_meta.get("phone", "(555) 010-1234")
    mrn = note_meta.get("mrn", "MRN-123456")
    addr = note_meta.get("address", "1 Main St, Boston, MA")
    header = f"From: {name} <{email}>\nTo: Records Office <records@example.gov>\nSubject: Discharge Summary\n"
    table = f"| Field | Value |\n|---|---|\n| Name | {name} |\n| Email | {email} |\n| Phone | {phone} |\n| MRN | {mrn} |\n| Address | {addr} |\n"
    fence = f"```\nMRN={mrn}\nPHONE={phone}\n```"
    body = note_meta.get("body", "")
    return header + "\n" + table + "\nNotes:\n" + body + "\n\n" + fence

def render_codeblock_wrapper(text: str) -> str:
    return "```\n{}\n```".format(text)
