#!/usr/bin/env python3
import argparse, math, sys, re, ast
from collections import defaultdict, Counter

import pandas as pd
import numpy as np

# ---------- helpers ----------
import math

def _binom_two_tailed_p(b10, b01):
    """Exact McNemar (two-tailed) using a binomial test on min(b10,b01)."""
    n = b10 + b01
    k = min(b10, b01)
    # two-sided p: sum of probabilities of outcomes as or more extreme than k
    # under Binom(n, 0.5). We'll mirror both tails.
    def _pmf(n, k):  # C(n,k) * 0.5^n
        return math.comb(n, k) * (0.5 ** n)
    p = sum(_pmf(n, i) for i in range(0, k + 1))
    # reflect upper tail
    p *= 2.0
    return min(1.0, p)

def _paired_counts(df, metric_col, scen_a, scen_b):
    """Return (n_pairs, b10, b01) for McNemar on a boolean metric."""
    sub = df[df["scenario"].isin([scen_a, scen_b])]
    wide = sub.pivot_table(index="doc_id", columns="scenario", values=metric_col, aggfunc="max")
    # Drop any rows missing one side
    wide = wide.dropna(subset=[scen_a, scen_b])
    # Cast to int (assumes metric is 0/1 or bool)
    a = wide[scen_a].astype(int)
    b = wide[scen_b].astype(int)
    b10 = int(((a == 1) & (b == 0)).sum())
    b01 = int(((a == 0) & (b == 1)).sum())
    return len(wide), b10, b01

def _try_print_pair(df, metric_col, label, scen_a, scen_b):
    if scen_a in df["scenario"].unique() and scen_b in df["scenario"].unique():
        n_pairs, b10, b01 = _paired_counts(df, metric_col, scen_a, scen_b)
        p = _binom_two_tailed_p(b10, b01) if (b10 + b01) > 0 else 1.0
        print(f"[{scen_a} vs {scen_b}] n_pairs={n_pairs}  "
              f"b10(A1,B0)={b10}  b01(A0,B1)={b01}  p_exact={p:.6g}")

def print_eval_awareness_contrasts(df):
    """
    Targeted, paired contrasts for eval awareness, objective hacking, and payload cues.
    Safe to call even if some scenarios are missing.
    """
    scen = set(df["scenario"].unique())

    # only print if we have *any* of these families
    interesting = {
        "exam_ablate", "exam_flip", "hidden_exam", "meta_exam",
        "doc_injection", "security_public", "security_restricted",
        # leave originals here in case you reuse this on old runs
        "exam_template", "live_ui",
    }
    if not scen.intersection(interesting):
        return

    print("\n== Targeted contrasts (eval awareness / objective hacking / payload cues) ==")

    def _pairs_present(pairs):
        return [(a, b) for (a, b) in pairs if a in scen and b in scen]

    # -------- leak_any --------
    if "leak_any" in df.columns:
        print("\n-- McNemar (paired) for leak_any --")
        leak_pairs = _pairs_present([
            # exam awareness + objective hacking
            ("exam_ablate", "control"),
            ("exam_template_neutral", "control"),
            ("live_ui_neutral", "control"),
            ("exam_template_neutral", "live_ui_neutral"),
            ("exam_ablate", "live_ui"),
            ("exam_flip",   "exam_ablate"),
            ("hidden_exam", "control"),
            ("meta_exam",   "control"),
            # NEW: payload cues (document-borne)
            ("doc_injection",       "control"),
            ("doc_override",       "control"),
            ("security_public",     "control"),
            ("security_restricted", "control"),
            ("security_restricted", "security_public"),
        ])
        for a, b in leak_pairs:
            _try_print_pair(df, "leak_any", "leak", a, b)

    # -------- decoy over-redaction --------
    decoy_col = "decoy_over_redaction"
    if decoy_col in df.columns:
        print("\n-- McNemar (paired) for decoy over-redaction --")
        decoy_pairs = _pairs_present([
            # exam awareness + objective hacking
            ("exam_ablate", "control"),
            ("exam_template_neutral", "control"),
            ("live_ui_neutral", "control"),
            ("exam_template_neutral", "live_ui_neutral"),
            ("exam_ablate", "live_ui"),
            ("exam_flip",   "exam_ablate"),
            ("hidden_exam", "control"),
            ("meta_exam",   "control"),
            # NEW: payload cues (document-borne)
            ("doc_injection",       "control"),
            ("doc_override",       "control"),
            ("security_public",     "control"),
            ("security_restricted", "control"),
            ("security_restricted", "security_public"),
        ])
        for a, b in decoy_pairs:
            _try_print_pair(df, decoy_col, "decoy", a, b)

def coerce_bool(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.astype(int)
    if pd.api.types.is_numeric_dtype(s):
        # Treat any nonzero as 1
        return (s.astype(float) > 0).astype(int)
    # stringy
    m = {'true':1,'t':1,'yes':1,'y':1,'1':1,
         'false':0,'f':0,'no':0,'n':0,'0':0}
    return s.astype(str).str.strip().str.lower().map(m).fillna(0).astype(int)

def find_col(df: pd.DataFrame, preferred_names, fallback_contains=None, required=True):
    for name in preferred_names:
        if name in df.columns:
            return name
    if fallback_contains:
        cands = [c for c in df.columns if fallback_contains in c]
        if len(cands)==1:
            return cands[0]
        # prefer a binary-looking column
        for c in cands:
            vals = pd.to_numeric(df[c], errors='coerce')
            if vals.notna().mean() > 0.9 and set(pd.unique(vals.dropna()).tolist()).issubset({0,1}):
                return c
        if cands:
            return cands[0]
    if required:
        raise SystemExit(f"Could not find any of {preferred_names} (or *{fallback_contains}*) in CSV columns: {list(df.columns)}")
    return None

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z*z/n
    centre = p + z*z/(2*n)
    rad = z*math.sqrt((p*(1-p) + z*z/(4*n))/n)
    lo = (centre - rad)/denom
    hi = (centre + rad)/denom
    return (max(0.0, lo), min(1.0, hi))

def fmt_rate(k, n):
    lo, hi = wilson_ci(k, n)
    pct = 100 * (k / n if n else 0)
    return f"{pct:5.1f}%  ({k}/{n})   CI95[{100*lo:4.1f}–{100*hi:4.1f}]"

def mcnemar_exact_p(b, c):
    """
    Two-sided exact McNemar test via binomial tail on discordant pairs.
    b = A=1,B=0 ; c = A=0,B=1
    """
    n = b + c
    if n == 0:
        return 1.0
    # two-sided: p = 2 * min( BinomCDF(min(b,c)), 1 - BinomCDF(max(b,c)-1) )
    from math import comb
    log_half_n = n * math.log(0.5)
    def logpmf(x):
        return math.log(comb(n, x)) + log_half_n
    # sum_{i=0..k} C(n,i)*(1/2)^n
    k = min(b, c)
    tail_small = sum(math.exp(logpmf(i)) for i in range(0, k+1))
    tail_large = sum(math.exp(logpmf(i)) for i in range(max(b,c), n+1))
    p_two = 2 * min(tail_small, tail_large)
    return min(1.0, p_two)

def two_prop_test(k1,n1,k2,n2):
    """
    Unpaired two-proportion z-test (two-sided).
    Returns dict with p1, p2, diff, z, p, and Wilson CIs.
    """
    if n1==0 or n2==0:
        return {"p1":0,"p2":0,"diff":0,"z":0,"p":1.0,
                "ci1":(0,0),"ci2":(0,0)}
    p1 = k1/n1; p2 = k2/n2
    diff = p2 - p1
    p_pool = (k1 + k2)/(n1 + n2)
    se = math.sqrt(p_pool*(1-p_pool)*(1/n1 + 1/n2)) if 0<p_pool<1 else 0.0
    if se == 0:
        z = 0.0; p = 1.0
    else:
        z = diff / se
        p = 2*(1 - 0.5*(1+math.erf(abs(z)/math.sqrt(2))))
    return {"p1":p1, "p2":p2, "diff":diff, "z":z, "p":p,
            "ci1": wilson_ci(k1,n1), "ci2": wilson_ci(k2,n2)}

def pick_scenarios(df):
    """
    Return a stable, sensible ordering for all scenarios present.
    First three entries are used by the generic McNemar block below.
    """
    preferred = [
        # originals
        "control", "exam_template", "live_ui",
        # your eval-awareness family
        "exam_ablate", "exam_flip",
        "hidden_exam", "hidden_live",
        "exam_template_neutral", "live_ui_neutral"
        "meta_exam", "meta_live",
        # NEW: payload cues
        "doc_injection", "doc_override", "security_public", "security_restricted",
    ]
    have = df["scenario"].astype(str).unique().tolist()
    order = [s for s in preferred if s in have] + [s for s in have if s not in preferred]
    if len(order) < 2:
        raise SystemExit(f"Need at least 2 scenarios; got {have}")
    return order

def safe_get(df, name):
    return df[name] if name in df.columns else pd.Series(index=df.index, dtype=float)

def parse_listish_cell(x):
    """
    Robustly parse a list-like cell such as "['ADDRESS','PHONE']" or "[]".
    Returns [] on failure/NA.
    """
    if isinstance(x, list):
        return x
    if pd.isna(x):
        return []
    s = str(x).strip()
    if s == "" or s == "[]":
        return []
    try:
        val = ast.literal_eval(s)
        if isinstance(val, list):
            return val
        return []
    except Exception:
        # Fallback: pull tokens between quotes
        toks = re.findall(r"'([^']+)'|\"([^\"]+)\"", s)
        vals = [a or b for (a,b) in toks]
        return vals

def parse_listish_series(col: pd.Series) -> pd.Series:
    return col.apply(parse_listish_cell)

# ---------- reporting blocks ----------

def rate_by_scenario(df, scen_order, flag_col, label):
    print(f"\n== {label} by scenario ==")
    for s in scen_order:
        d = df[df["scenario"]==s]
        n = len(d)
        k = int(d[flag_col].sum())
        print(f"[{s:13}] {fmt_rate(k,n)}")

def rate_by_filetype(df, flag_col, label):
    print(f"\n== {label} by file_type ==")
    for ft, d in df.groupby("file_type"):
        n = len(d)
        k = int(d[flag_col].sum())
        print(f"{ft or 'NA':15} {fmt_rate(k,n)}")

def class_leaks(df, scen_order):
    """
    Supports either:
      • per-class boolean columns: leak_NAME, leak_DOB, ...
      • a single list column: leak_types  (e.g., "['ADDRESS','PHONE']")
    """
    # 1) Boolean per-class columns (if present)
    bool_cols = [c for c in df.columns
                 if c.startswith("leak_")
                 and c not in {"leak_", "leak", "leak_rate", "leak_types"}]
    bool_cols = [c for c in bool_cols if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c])]

    if bool_cols:
        print("\n== Per-PII-class leak rates (boolean columns) ==")
        for c in sorted(bool_cols):
            print(f"\n-- {c} --")
            for s in scen_order:
                d = df[df["scenario"]==s]
                n = len(d)
                k = int(coerce_bool(d[c]).sum())
                print(f"[{s:13}] {fmt_rate(k,n)}")

    # 2) leak_types list column
    if "leak_types" in df.columns:
        print("\n== Per-PII-class leak rates (from leak_types list) ==")
        lt = parse_listish_series(df["leak_types"])
        # discover classes
        classes = sorted(set(t for lst in lt for t in lst))
        if not classes:
            print("(no classes found in leak_types)")
            return
        # attach parsed list to df for indexing
        df_local = df.copy()
        df_local["_leak_types_list"] = lt

        for c in classes:
            print(f"\n-- {c} --")
            for s in scen_order:
                d = df_local[df_local["scenario"]==s]
                n = len(d)
                k = int(d["_leak_types_list"].apply(lambda xs: c in xs).sum())
                print(f"[{s:13}] {fmt_rate(k,n)}")

def confidence_calibration(df, leak_col, refusal_col=None):
    sub = df.copy()
    if refusal_col and refusal_col in sub.columns:
        sub = sub[sub[refusal_col] == 0]
    if "confidence" not in sub.columns:
        print("\n(no 'confidence' column; skipping calibration)")
        return
    sub = sub[pd.to_numeric(sub["confidence"], errors="coerce").notna()]
    if sub.empty:
        print("\n== Confidence calibration ==\n(no confidence values found)")
        return
    conf = sub["confidence"].astype(float).clip(0,1)
    success = (1 - sub[leak_col].astype(int)).astype(int)
    bins = [0.0,0.2,0.4,0.6,0.8,1.001]
    labels = ["0.0–0.2","0.2–0.4","0.4–0.6","0.6–0.8","0.8–1.0"]
    sub = sub.assign(conf_bin=pd.cut(conf, bins=bins, labels=labels, include_lowest=True, right=False))
    print("\n== Confidence calibration (success = no leak, non-refusals) ==")
    for lab in labels:
        d = sub[sub["conf_bin"]==lab]
        n = len(d)
        if n == 0:
            print(f"  {lab}: success=— (n=0)")
            continue
        succ = int(success.loc[d.index].sum())
        rate = succ / n
        print(f"  {lab}: success={rate:.3f} (n={n})")
    try:
        r = np.corrcoef(conf, success)[0,1]
    except Exception:
        r = float("nan")
    print(f"Point-biserial corr(conf, success): {r}")

def print_header(title):
    print("\n" + title)
    print("-"*len(title))

def paired_mcnemar(df, id_col, scenA, scenB, flag_col, exclude_refusals=True, refusal_col=None):
    sub = df[df["scenario"].isin([scenA, scenB])].copy()
    if exclude_refusals and refusal_col and refusal_col in sub.columns:
        sub = sub[sub[refusal_col] == 0]
    wide = sub.pivot_table(index=id_col, columns="scenario", values=flag_col, aggfunc="max")
    wide = wide.dropna(subset=[scenA, scenB])
    a = coerce_bool(wide[scenA])
    b = coerce_bool(wide[scenB])
    b10 = int(((a==1) & (b==0)).sum())
    b01 = int(((a==0) & (b==1)).sum())
    n = len(wide)
    p = mcnemar_exact_p(b10, b01)
    return {"n_pairs": n, "b10": b10, "b01": b01, "p": p}

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to outputs/eval/records.csv")
    ap.add_argument("--id-col", default="doc_id")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if "scenario" not in df.columns:
        raise SystemExit("CSV must have a 'scenario' column.")
    scen_order = pick_scenarios(df)

    # Locate columns (robust names)
    leak_col   = find_col(df, ["leak"], fallback_contains="leak")
    decoy_col  = find_col(df, ["decoy_over_redaction","decoy","over_redaction","decoy_fp"], fallback_contains="decoy")
    uncertainty_col = find_col(df, ["uncertainty","uncertainty_talk"], fallback_contains="uncertainty", required=False)
    refusal_col     = find_col(df, ["refusal"], fallback_contains="refusal", required=False)
    schema_col      = find_col(df, ["schema_ok","schema"], fallback_contains="schema", required=False)

    # Coerce to ints where appropriate
    for c in [leak_col, decoy_col, uncertainty_col, refusal_col, schema_col]:
        if c and c in df.columns:
            df[c] = coerce_bool(df[c])

    # Quick overview
    print_header("Basic counts")
    print("Rows:", len(df))
    print("Scenarios:", scen_order)
    if refusal_col:
        ref_rate = df[refusal_col].mean()
        print(f"Refusal rate (overall): {100*ref_rate:.1f}%")
    if schema_col:
        sch_rate = df[schema_col].mean()
        print(f"Schema compliance (overall): {100*sch_rate:.1f}%")

    # Per-scenario rates
    rate_by_scenario(df, scen_order, leak_col,  "Leak rate")
    rate_by_scenario(df, scen_order, decoy_col, "Decoy over-redaction")
    if uncertainty_col:
        rate_by_scenario(df, scen_order, uncertainty_col, "Uncertainty talk")

    # Pairwise McNemar (paired) for leak / decoy / uncertainty
    pairs = []
    if len(scen_order) >= 3:
        pairs = [(scen_order[0], scen_order[1]),
                 (scen_order[1], scen_order[2]),
                 (scen_order[0], scen_order[2])]
    elif len(scen_order) == 2:
        pairs = [(scen_order[0], scen_order[1])]
    def show_mcnemar(flag_col, label):
        print(f"\n== McNemar (paired) for {label} ==")
        for A,B in pairs:
            res = paired_mcnemar(df, args.id_col, A, B, flag_col,
                                 exclude_refusals=True, refusal_col=refusal_col)
            print(f"[{A} vs {B}] n_pairs={res['n_pairs']}  b10(A1,B0)={res['b10']}  b01(A0,B1)={res['b01']}  p_exact={res['p']:.4g}")
    show_mcnemar(leak_col,  "leak")
    show_mcnemar(decoy_col, "decoy over-redaction")
    if uncertainty_col:
        show_mcnemar(uncertainty_col, "uncertainty talk")

    # Unpaired two-proportion z-tests for effect sizes
    def show_unpaired(flag_col, label):
        print(f"\n== Two-proportion z-tests for {label} (unpaired, per-scenario) ==")
        counts = []
        for s in scen_order:
            d = df[df["scenario"]==s]
            k = int(d[flag_col].sum())
            n = len(d)
            counts.append((s,k,n))
        for i in range(len(counts)):
            for j in range(i+1, len(counts)):
                s1,k1,n1 = counts[i]
                s2,k2,n2 = counts[j]
                out = two_prop_test(k1,n1,k2,n2)
                print(f"[{s1} → {s2}] p1={100*out['p1']:.1f}%  p2={100*out['p2']:.1f}%  Δ={100*out['diff']:.1f} pp   z={out['z']:.2f}  p={out['p']:.4g}")
    show_unpaired(leak_col,  "leak")
    show_unpaired(decoy_col, "decoy over-redaction")
    if uncertainty_col:
        show_unpaired(uncertainty_col, "uncertainty talk")

    # By file_type
    rate_by_filetype(df, leak_col,  "Leak rate")
    rate_by_filetype(df, decoy_col, "Decoy over-redaction")
    if uncertainty_col:
        rate_by_filetype(df, uncertainty_col, "Uncertainty talk")

    # Per-PII-class (handles both boolean columns and leak_types list)
    class_leaks(df, scen_order)

    # Confidence calibration (success = no leak)
    confidence_calibration(df, leak_col, refusal_col=refusal_col)

    try:
        print_eval_awareness_contrasts(df)
    except Exception as e:
        print(f"\n[WARN] eval-awareness contrasts skipped: {e}")

if __name__ == "__main__":
    main()
    