# Synthetic Data Generation Package: Script and Function Reference

This document describes every script and function in the `scripts/` directory as they relate to synthetic PII data generation. Each function is explained in context, with its role in the data pipeline.

---

## scripts/generate_local.py
**Main entry point for local synthetic data generation.**
- Creates realistic patient and encounter text, seeds PII spans, mixes in clinical content, adds decoy look-alikes, and writes output files.
- Produces variants: plain, formatted, obfuscated, mixed.
- Writes `data/items.jsonl` and per-bundle ground truth.

### Key Functions:
- `main()`: Orchestrates the entire generation process, loads config, sets up RNGs, iterates over bundles, calls renderers, writes outputs.
- `_append_ground_truth(gt_dir: Path, row: dict)`: Writes ground truth PII/decoy spans for each bundle to `redact.jsonl`.
- `load_yaml(path: Path)`: Loads YAML config files.
- `ensure_faker(seed: int)`: Ensures the `faker` library is installed and returns a seeded Faker instance.

---

## scripts/_formats.py
**Format-specific note/document renderer.**
- Uses helpers and config knobs for high-variability, deterministic output.
- Handles section shuffling, filler, bullets, blurbs, PII block placement, and decoy insertion.

### Key Functions:
- `render_note(meta, out_dir, idx, rng)`: Renders a clinical note with variable sections, PII blocks, filler, bullets, intro/outro blurbs, and decoy content.
- `_DEF_DECOY(rng)`: Generates a deterministic decoy string.
- `_DEF_SPAN(text, value, typ)`: Finds and returns a PII span for a value in text.
- `_DEF_DECOY_SPAN(text, marker)`: Finds and returns a decoy span for a marker in text.

---

## scripts/_noise.py
**Helpers for text variability and noise.**
- Provides synonyms, filler sentences, bullets, and text jitter/hyphenation utilities.

### Key Functions:
- `pick(rng, seq)`: Picks a random element from a sequence.
- `some(rng, seq, kmin=1, kmax=3)`: Picks a random sample of elements from a sequence.
- `jitter_whitespace(rng, text)`: Randomly inserts blank lines and trailing spaces.
- `hyphenate_randomly(rng, text, p=0.1)`: Randomly hyphenates long words in text.
- `mk_paragraph(rng, lead, body)`: Formats a paragraph with a lead and body.
- `mk_bullets(rng)`: Generates a list of bullet points.

---

## scripts/_textbank.py
**Templates and blurbs for note generation.**
- Provides section templates, intro/outro blurbs, and KV fences for PII block placement.

### Key Data:
- `TEMPLATES_NOTE`: List of note section templates.
- `INTRO_BLURBS`: List of intro blurbs for notes.
- `OUTRO_BLURBS`: List of outro blurbs for notes.
- `KV_FENCES`: List of code fence templates for PII blocks.

---

## scripts/_util.py
**Utility functions for file writing.**

### Key Functions:
- `write_jsonl(path, items)`: Writes a list of dicts to a JSONL file.

---

## scripts/_variants.py
**Document variant renderers.**
- Produces plain, formatted, mixed, and codeblock-wrapped variants for each note.

### Key Functions:
- `render_mixed(note_meta, rng)`: Composes a document with multiple non-PII structures.
- `render_plain(note)`: Returns the note as-is.
- `render_formatted(note_meta)`: Renders fields as markdown table, email header, and code block.
- `render_codeblock_wrapper(text)`: Wraps text in a code block.

---

## scripts/_spans.py
**Span-finding utilities for PII and decoy detection.**
- Finds literal spans, decoy spans, and format-specific PII spans in text.

### Key Functions:
- `_find_all(text, needle)`: Finds all occurrences of a substring in text.
- `spans_literal(text, value, typ)`: Finds all literal spans of a value in text.
- `span_decoy(text, marker, label)`: Finds all decoy spans in text.
- `hl7_name_spans(text, full_name)`: Finds HL7-style name spans.
- `hl7_dob_spans(text, dob_iso)`: Finds HL7-style DOB spans.
- `hl7_address_spans(text, ...)`: Finds HL7-style address spans.
- `hl7_phone_spans(text, phone_digits)`: Finds HL7-style phone spans.

---

## scripts/_obfuscation.py
**Text obfuscation utilities.**
- Inserts zero-width characters, replaces with homoglyphs, and spaces out digits for obfuscation.

### Key Functions:
- `insert_zero_width(s, p=0.15, rng=None)`: Inserts zero-width characters into text.
- `replace_homoglyphs(s, p=0.2, rng=None)`: Replaces characters with visually similar homoglyphs.
- `space_out_digits(s, gap=" ")`: Spaces out digit sequences in text.
- `obfuscate_text(s, rng=None)`: Applies all obfuscation steps to text.

---

# End of Script and Function Reference
