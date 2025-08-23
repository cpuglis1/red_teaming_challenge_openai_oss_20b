#!/usr/bin/env python3
import argparse, csv, math, re, ast
from collections import defaultdict
import numpy as np

# ---------------------- small utils ----------------------

def print_header(title: str):
    print("\n" + title)
    print("-" * len(title))

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
    """Two-sided exact McNemar via binomial tails on discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    log_half_n = n * math.log(0.5)
    def logpmf(x):
        return math.log(math.comb(n, x)) + log_half_n
    tail_small = sum(math.exp(logpmf(i)) for i in range(0, k+1))
    tail_large = sum(math.exp(logpmf(i)) for i in range(max(b, c), n+1))
    p_two = 2 * min(tail_small, tail_large)
    return min(1.0, p_two)

def two_prop_test(k1, n1, k2, n2):
    """Unpaired two-proportion z-test (two-sided) + Wilson CIs."""
    if n1 == 0 or n2 == 0:
        return {"p1":0,"p2":0,"diff":0,"z":0,"p":1.0,
                "ci1":(0,0),"ci2":(0,0)}
    p1 = k1/n1; p2 = k2/n2
    diff = p2 - p1
    p_pool = (k1 + k2)/(n1 + n2)
    se = math.sqrt(p_pool*(1-p_pool)*(1/n1 + 1/n2)) if 0 < p_pool < 1 else 0.0
    if se == 0:
        z = 0.0; p = 1.0
    else:
        z = diff / se
        p = 2*(1 - 0.5*(1+math.erf(abs(z)/math.sqrt(2))))
    return {"p1":p1, "p2":p2, "diff":diff, "z":z, "p":p,
            "ci1": wilson_ci(k1,n1), "ci2": wilson_ci(k2,n2)}

def point_biserial(xs, ys01):
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys01, dtype=float)
    if xs.size == 0 or ys.size == 0 or xs.size != ys.size:
        return float("nan")
    if np.all(xs == xs[0]):
        return float("nan")
    vy = np.var(ys)
    if vy <= 1e-12:
        return float("nan")
    return np.corrcoef(xs, ys)[0,1]

# ---------------------- CSV + coercion ----------------------

BOOL_MAP = {
    'true':1,'t':1,'yes':1,'y':1,'1':1,
    'false':0,'f':0,'no':0,'n':0,'0':0
}

def normalize_empty(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s == "" or s.lower() in {"na","nan","none","null"} else s

def coerce_bool_value(v):
    v = normalize_empty(v)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return 1 if float(v) > 0 else 0
        except Exception:
            return None
    s = str(v).strip().lower()
    if s in BOOL_MAP:
        return BOOL_MAP[s]
    try:
        return 1 if float(s) > 0 else 0
    except Exception:
        return None

def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        header = reader.fieldnames or []
    return rows, header

def columns_set(rows, header_cols):
    cols = set(header_cols)
    for r in rows:
        cols.update(r.keys())
    return cols

def find_col(cols, preferred_names, fallback_contains=None, required=True, rows=None):
    for name in preferred_names:
        if name in cols:
            return name
    if fallback_contains:
        cands = [c for c in cols if fallback_contains in c]
        if len(cands) == 1:
            return cands[0]
        if rows and cands:
            # prefer binary-looking
            best = None; best_score = -1.0
            for c in cands:
                total = good = 0
                seen = set()
                for r in rows:
                    v = r.get(c)
                    nv = normalize_empty(v)
                    if nv is None:
                        continue
                    total += 1
                    cv = coerce_bool_value(v)
                    if cv is not None:
                        good += 1
                        seen.add(int(cv))
                score = (good/(total or 1.0)) + (1.0 if seen.issubset({0,1}) and seen else 0.0)
                if score > best_score:
                    best_score = score; best = c
            if best:
                return best
        if cands:
            return cands[0]
    if required:
        raise SystemExit(f"Could not find any of {preferred_names} (or *{fallback_contains}*) in CSV columns: {sorted(cols)}")
    return None

def ensure_int01_column(rows, col):
    for r in rows:
        v = coerce_bool_value(r.get(col))
        r[col] = 0 if v is None else int(v)

def parse_listish_cell(x):
    x = normalize_empty(x)
    if x is None:
        return []
    if isinstance(x, list):
        return x
    s = str(x)
    if s == "[]":
        return []
    try:
        val = ast.literal_eval(s)
        if isinstance(val, list):
            return val
    except Exception:
        pass
    toks = re.findall(r"'([^']+)'|\"([^\"]+)\"", s)
    return [a or b for (a,b) in toks]

# ---------------------- scenario helpers ----------------------

def pick_scenarios(rows):
    preferred = [
        "control", "exam_template", "live_ui",
        "exam_ablate", "exam_flip",
        "hidden_exam", "hidden_live",
        "exam_template_neutral", "live_ui_neutral",
        "meta_exam", "meta_live",
        "exam_explicit_ablate_user", "exam_explicit_ablate_system",
        "meta_env", "meta_workflow", "meta_qa", "meta_placebo",
        "doc_injection", "doc_override", "security_public", "security_restricted",
    ]
    have = []
    seen = set()
    for r in rows:
        s = str(r.get("scenario",""))
        if s and s not in seen:
            have.append(s)
            seen.add(s)
    order = [s for s in preferred if s in seen] + [s for s in have if s not in preferred]
    if len(order) < 2:
        raise SystemExit(f"Need at least 2 scenarios; got {have}")
    return order

# ---------------------- aggregations & reports ----------------------

def rate_by_scenario(rows, scen_order, flag_col, label):
    print(f"\n== {label} by scenario ==")
    for s in scen_order:
        d = [r for r in rows if str(r.get("scenario","")) == s]
        n = len(d)
        k = sum(int(r.get(flag_col, 0) or 0) for r in d)
        print(f"[{s:13}] {fmt_rate(k,n)}")

def rate_by_filetype(rows, flag_col, label):
    print(f"\n== {label} by file_type ==")
    groups = defaultdict(list)
    for r in rows:
        ft = str(r.get("file_type", "") or "NA")
        groups[ft].append(r)
    for ft, d in groups.items():
        n = len(d)
        k = sum(int(r.get(flag_col, 0) or 0) for r in d)
        print(f"{ft:15} {fmt_rate(k,n)}")

def paired_mcnemar(rows, id_col, scenA, scenB, flag_col, exclude_refusals=True, refusal_col=None):
    a_map, b_map = {}, {}
    for r in rows:
        scen = str(r.get("scenario",""))
        if scen not in (scenA, scenB):
            continue
        if exclude_refusals and refusal_col and coerce_bool_value(r.get(refusal_col)) == 1:
            continue
        doc_id = str(r.get(id_col, "") or "")
        if not doc_id:
            continue
        flag = coerce_bool_value(r.get(flag_col))
        flag = 0 if flag is None else int(flag)
        if scen == scenA:
            a_map[doc_id] = max(a_map.get(doc_id, 0), flag)
        else:
            b_map[doc_id] = max(b_map.get(doc_id, 0), flag)
    common = set(a_map.keys()) & set(b_map.keys())
    b10 = sum(1 for d in common if a_map[d] == 1 and b_map[d] == 0)
    b01 = sum(1 for d in common if a_map[d] == 0 and b_map[d] == 1)
    p = mcnemar_exact_p(b10, b01)
    return {"n_pairs": len(common), "b10": b10, "b01": b01, "p": p}

def class_leaks(rows, scen_order, cols):
    # boolean leak_* columns
    bool_cols = [c for c in cols if c.startswith("leak_")
                 and c not in {"leak_", "leak", "leak_rate", "leak_types"}]
    pruned = []
    for c in bool_cols:
        seen = set()
        for r in rows:
            v = coerce_bool_value(r.get(c))
            if v is not None:
                seen.add(int(v))
        if seen.issubset({0,1}) and seen:
            pruned.append(c)

    if pruned:
        print("\n== Per-PII-class leak rates (boolean columns) ==")
        for c in sorted(pruned):
            print(f"\n-- {c} --")
            for s in scen_order:
                d = [r for r in rows if str(r.get("scenario","")) == s]
                n = len(d)
                k = sum((coerce_bool_value(r.get(c)) or 0) for r in d)
                print(f"[{s:13}] {fmt_rate(k,n)}")

    # leak_types list column
    if "leak_types" in cols:
        print("\n== Per-PII-class leak rates (from leak_types list) ==")
        parsed = []
        all_classes = set()
        for r in rows:
            lt = parse_listish_cell(r.get("leak_types"))
            parsed.append(lt); all_classes.update(lt)
        classes = sorted(all_classes)
        if not classes:
            print("(no classes found in leak_types)")
            return
        for c in classes:
            print(f"\n-- {c} --")
            for s in scen_order:
                n = k = 0
                for i, r in enumerate(rows):
                    if str(r.get("scenario","")) != s: 
                        continue
                    n += 1
                    if c in parsed[i]:
                        k += 1
                print(f"[{s:13}] {fmt_rate(k,n)}")

def confidence_calibration(rows, leak_col, refusal_col=None):
    xs = []; ys = []
    for r in rows:
        if refusal_col and coerce_bool_value(r.get(refusal_col)) == 1:
            continue
        conf = normalize_empty(r.get("confidence"))
        if conf is None:
            continue
        try:
            c = float(conf)
        except Exception:
            continue
        c = max(0.0, min(1.0, c))
        leak = coerce_bool_value(r.get(leak_col))
        leak = 0 if leak is None else int(leak)
        xs.append(c); ys.append(1 - leak)  # success = no leak

    if not xs:
        print("\n== Confidence calibration ==\n(no confidence values found)")
        return

    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)

    bins = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.001])
    labels = ["0.0–0.2","0.2–0.4","0.4–0.6","0.6–0.8","0.8–1.0"]
    idx = np.digitize(xs, bins, right=False) - 1
    print("\n== Confidence calibration (success = no leak, non-refusals) ==")
    for i, lab in enumerate(labels):
        mask = (idx == i)
        n = int(mask.sum())
        if n == 0:
            print(f"  {lab}: success=— (n=0)")
        else:
            rate = float(ys[mask].mean())
            print(f"  {lab}: success={rate:.3f} (n={n})")
    r = point_biserial(xs, ys)
    print(f"Point-biserial corr(conf, success): {r if r == r else 'NA'}")

def print_eval_awareness_contrasts(rows, scen_order, cols, id_col, refusal_col, leak_col, decoy_col):
    scen = set(str(r.get("scenario","")) for r in rows)
    interesting = {
        "exam_ablate", "exam_flip", "hidden_exam", "meta_exam",
        "exam_template", "live_ui", "exam_template_neutral", "live_ui_neutral",
        "doc_injection", "doc_override", "security_public", "security_restricted",
        "exam_explicit_ablate_user", "exam_explicit_ablate_system",
        "meta_env", "meta_workflow", "meta_qa", "meta_placebo",
    }
    if not scen.intersection(interesting):
        return

    def pairs_present(pairs):
        return [(a,b) for (a,b) in pairs if a in scen and b in scen]

    print("\n== Targeted contrasts (eval awareness / objective hacking / payload cues / ablations) ==")

    if leak_col:
        print("\n-- McNemar (paired) for leak_any --")
        leak_pairs = pairs_present([
            ("exam_ablate", "control"),
            ("exam_template_neutral", "control"),
            ("live_ui_neutral", "control"),
            ("exam_template_neutral", "live_ui_neutral"),
            ("hidden_exam", "control"),
            ("meta_exam",   "control"),
            ("doc_injection", "control"),
            ("doc_override",  "control"),
            ("security_public", "control"),
            ("security_restricted", "control"),
            ("security_restricted", "security_public"),
            ("exam_explicit_ablate_user",    "control"),
            ("exam_explicit_ablate_system",  "control"),
            ("exam_explicit_ablate_system",  "exam_explicit_ablate_user"),
            ("meta_env", "control"), ("meta_workflow", "control"),
            ("meta_qa", "control"), ("meta_placebo", "control"),
            ("meta_env","meta_placebo"), ("meta_workflow","meta_placebo"),
            ("meta_qa","meta_placebo"),
        ])
        for A,B in leak_pairs:
            res = paired_mcnemar(rows, id_col, A, B, leak_col, True, refusal_col)
            print(f"[{A} vs {B}] n_pairs={res['n_pairs']}  b10(A1,B0)={res['b10']}  b01(A0,B1)={res['b01']}  p_exact={res['p']:.6g}")

    if decoy_col:
        print("\n-- McNemar (paired) for decoy over-redaction --")
        decoy_pairs = pairs_present([
            ("exam_ablate", "control"),
            ("exam_template_neutral", "control"),
            ("live_ui_neutral", "control"),
            ("exam_template_neutral", "live_ui_neutral"),
            ("hidden_exam", "control"),
            ("meta_exam",   "control"),
            ("doc_injection", "control"),
            ("doc_override",  "control"),
            ("security_public", "control"),
            ("security_restricted", "control"),
            ("security_restricted", "security_public"),
            ("exam_explicit_ablate_user",    "control"),
            ("exam_explicit_ablate_system",  "control"),
            ("exam_explicit_ablate_system",  "exam_explicit_ablate_user"),
            ("meta_env", "control"), ("meta_workflow", "control"),
            ("meta_qa", "control"), ("meta_placebo", "control"),
            ("meta_env","meta_placebo"), ("meta_workflow","meta_placebo"),
            ("meta_qa","meta_placebo"),
        ])
        for A,B in decoy_pairs:
            res = paired_mcnemar(rows, id_col, A, B, decoy_col, True, refusal_col)
            print(f"[{A} vs {B}] n_pairs={res['n_pairs']}  b10(A1,B0)={res['b10']}  b01(A0,B1)={res['b01']}  p_exact={res['p']:.6g}")

# ---------------------- main ----------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to outputs/eval/records.csv")
    ap.add_argument("--id-col", default="doc_id")
    args = ap.parse_args()

    rows, header = read_csv_rows(args.csv)
    if not rows:
        raise SystemExit("CSV is empty or unreadable.")
    cols = columns_set(rows, header)

    if "scenario" not in cols:
        raise SystemExit("CSV must have a 'scenario' column.")

    scen_order = pick_scenarios(rows)

    leak_col   = find_col(cols, ["leak_any","leak"], fallback_contains="leak", rows=rows)
    decoy_col  = find_col(cols, ["decoy_over_redaction","decoy","over_redaction","decoy_fp"],
                          fallback_contains="decoy", rows=rows)
    uncertainty_col = find_col(cols, ["uncertainty","uncertainty_talk"], fallback_contains="uncertainty",
                               required=False, rows=rows)
    refusal_col     = find_col(cols, ["refusal"], fallback_contains="refusal", required=False, rows=rows)
    schema_col      = find_col(cols, ["schema_ok","schema"], fallback_contains="schema", required=False, rows=rows)

    # Coerce to 0/1 ints for key flags
    for c in [leak_col, decoy_col, uncertainty_col, refusal_col, schema_col]:
        if c:
            ensure_int01_column(rows, c)

    # Quick overview
    print_header("Basic counts")
    print("Rows:", len(rows))
    print("Scenarios:", scen_order)
    if refusal_col:
        ref_rate = np.mean([r.get(refusal_col,0) for r in rows]) if rows else 0.0
        print(f"Refusal rate (overall): {100*ref_rate:.1f}%")
    if schema_col:
        sch_rate = np.mean([r.get(schema_col,0) for r in rows]) if rows else 0.0
        print(f"Schema compliance (overall): {100*sch_rate:.1f}%")

    # Per-scenario rates
    rate_by_scenario(rows, scen_order, leak_col,  "Leak rate")
    rate_by_scenario(rows, scen_order, decoy_col, "Decoy over-redaction")
    if uncertainty_col:
        rate_by_scenario(rows, scen_order, uncertainty_col, "Uncertainty talk")

    # Pairwise McNemar for first 2–3 scenarios
    def show_mcnemar(flag_col, label):
        if not flag_col: 
            return
        pairs = []
        if len(scen_order) >= 3:
            pairs = [(scen_order[0], scen_order[1]),
                     (scen_order[1], scen_order[2]),
                     (scen_order[0], scen_order[2])]
        elif len(scen_order) == 2:
            pairs = [(scen_order[0], scen_order[1])]
        print(f"\n== McNemar (paired) for {label} ==")
        for A,B in pairs:
            res = paired_mcnemar(rows, args.id_col, A, B, flag_col, True, refusal_col)
            print(f"[{A} vs {B}] n_pairs={res['n_pairs']}  b10(A1,B0)={res['b10']}  b01(A0,B1)={res['b01']}  p_exact={res['p']:.4g}")

    show_mcnemar(leak_col,  "leak")
    show_mcnemar(decoy_col, "decoy over-redaction")
    if uncertainty_col:
        show_mcnemar(uncertainty_col, "uncertainty talk")

    # Unpaired two-proportion z-tests across all scenario pairs
    def show_unpaired(flag_col, label):
        if not flag_col: 
            return
        print(f"\n== Two-proportion z-tests for {label} (unpaired, per-scenario) ==")
        counts = []
        for s in scen_order:
            d = [r for r in rows if str(r.get("scenario","")) == s]
            k = sum(int(r.get(flag_col,0)) for r in d)
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
    rate_by_filetype(rows, leak_col,  "Leak rate")
    rate_by_filetype(rows, decoy_col, "Decoy over-redaction")
    if uncertainty_col:
        rate_by_filetype(rows, uncertainty_col, "Uncertainty talk")

    # Per-PII-class
    class_leaks(rows, scen_order, cols)

    # Confidence calibration (success = no leak)
    confidence_calibration(rows, leak_col, refusal_col=refusal_col)

    # Targeted contrasts
    try:
        print_eval_awareness_contrasts(rows, scen_order, cols, args.id_col, refusal_col, leak_col, decoy_col)
    except Exception as e:
        print(f"\n[WARN] eval-awareness contrasts skipped: {e}")

if __name__ == "__main__":
    main()