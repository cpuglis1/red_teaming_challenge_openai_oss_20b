# scripts/_obfuscation.py
# SPDX-License-Identifier: Apache-2.0
import random

ZW_SEQ = ["\u200b", "\u200c", "\u200d", "\u2060"]
HOMO = {
    "A": "Α", "B": "Β", "E": "Ε", "H": "Η", "I": "Ι", "K": "Κ", "M": "Μ", "N": "Ν", "O": "Ο",
    "P": "Ρ", "T": "Τ", "X": "Χ", "Y": "Υ",
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х"
}  # Greek/Cyrillic homoglyphs (visual look-alikes)

def insert_zero_width(s: str, p: float = 0.15, rng: random.Random | None = None) -> str:
    rng = rng or random
    out = []
    for ch in s:
        out.append(ch)
        if ch.isalnum() and rng.random() < p:
            out.append(rng.choice(ZW_SEQ))
    return "".join(out)

def replace_homoglyphs(s: str, p: float = 0.2, rng: random.Random | None = None) -> str:
    rng = rng or random
    return "".join(HOMO.get(ch, ch) if ch in HOMO and rng.random() < p else ch for ch in s)

def space_out_digits(s: str, gap: str = " ") -> str:
    out, buf = [], []
    for ch in s:
        if ch.isdigit():
            buf.append(ch)
        else:
            if buf:
                out.append(gap.join(buf)); buf = []
            out.append(ch)
    if buf:
        out.append(gap.join(buf))
    return "".join(out)

def obfuscate_text(s: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    s = insert_zero_width(s, p=0.2, rng=rng)
    s = replace_homoglyphs(s, p=0.15, rng=rng)
    s = space_out_digits(s)
    return s
