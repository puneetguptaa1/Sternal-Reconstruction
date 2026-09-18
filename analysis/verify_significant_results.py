#!/usr/bin/env python3
"""Independent re-derivation of every significant pooled estimate.

Deliberately does NOT import the pipeline: the 2x2 tables and arm summaries are
rebuilt from meta_analysis_data.csv and the raw sheets, and the estimators are
written out again from the eMethods description. Any disagreement beyond
rounding is a real defect.
"""
import numpy as np, pandas as pd
from scipy import stats
from collections import defaultdict

CONT = {"Op Time", "LOS"}
raw = pd.read_csv("meta_analysis_data.csv")
sig = pd.read_csv("results_significant.csv")

def arms(g, cont):
    per = {}
    for (sid, name), s in g.groupby(["study_id", "study_name"]):
        a = s[s.comp_arm == "comp1"]; b = s[s.comp_arm == "comp2"]
        if a.empty or b.empty: continue
        rec = {}
        ok = True
        for tag, df in (("1", a), ("2", b)):
            n = df.n.sum()
            if cont:
                m = df.val.values.astype(float); ns = df.n.values.astype(float)
                sd = df.sd.values.astype(float)
                if np.any(np.isnan(m)) or np.any(np.isnan(sd)): ok = False; break
                mean = (ns * m).sum() / n
                var = ((ns * sd**2).sum() + (ns * (m - mean)**2).sum()) / n
                if np.sqrt(var) == 0 or n == 1: ok = False; break
                rec[tag] = (n, mean, np.sqrt(var))
            else:
                rec[tag] = (n, df.val.sum())
        if ok and len(rec) == 2: per[name] = rec
    return per

def mh(per):
    est = []
    for nm, r in per.items():
        (n1, e1), (n2, e2) = r["1"], r["2"]
        a, b, c, dd = e1, n1 - e1, e2, n2 - e2
        if (a == 0 and c == 0) or (b == 0 and dd == 0): continue
        if 0 in (a, b, c, dd): a, b, c, dd = a + .5, b + .5, c + .5, dd + .5
        est.append((a, b, c, dd))
    k = len(est)
    if k < 2: return None
    N = [sum(t) for t in est]
    R = [t[0] * t[3] / n for t, n in zip(est, N)]
    S = [t[1] * t[2] / n for t, n in zip(est, N)]
    v = [1/t[0] + 1/t[1] + 1/t[2] + 1/t[3] for t in est]
    y = [np.log((t[0]*t[3])/(t[1]*t[2])) for t in est]
    w = [1/x for x in v]
    fe = sum(wi*yi for wi, yi in zip(w, y)) / sum(w)
    Q = sum(wi*(yi-fe)**2 for wi, yi in zip(w, y))
    if k == 2:
        OR = sum(R)/sum(S); lo = np.log(OR)
        P = [(t[0]+t[3])/n for t, n in zip(est, N)]
        Qq = [(t[1]+t[2])/n for t, n in zip(est, N)]
        var = (sum(p*r for p, r in zip(P, R))/(2*sum(R)**2)
               + sum(p*s + q*r for p, s, q, r in zip(P, S, Qq, R))/(2*sum(R)*sum(S))
               + sum(q*s for q, s in zip(Qq, S))/(2*sum(S)**2))
        se = np.sqrt(var)
    else:
        C = sum(w) - sum(x*x for x in w)/sum(w)
        t2 = max(0, (Q-(k-1))/C) if C > 0 else 0
        w2 = [1/(1/wi + t2) for wi in w]
        lo = sum(wi*yi for wi, yi in zip(w2, y))/sum(w2)
        se = np.sqrt(1/sum(w2))
    z = lo/se
    return k, np.exp(lo), np.exp(lo-1.96*se), np.exp(lo+1.96*se), \
           2*(1-stats.norm.cdf(abs(z))), max(0,(Q-(k-1))/Q)*100 if Q > 0 else 0

def iv(per):
    y, se = [], []
    for nm, r in per.items():
        (n1, m1, s1), (n2, m2, s2) = r["1"], r["2"]
        y.append(m1-m2); se.append(np.sqrt(s1**2/n1 + s2**2/n2))
    k = len(y)
    if k < 2: return None
    y = np.array(y); se = np.array(se); w = 1/se**2
    fe = (w*y).sum()/w.sum(); Q = (w*(y-fe)**2).sum()
    if k == 2:
        est = fe; s = np.sqrt(1/w.sum())
    else:
        C = w.sum() - (w**2).sum()/w.sum()
        t2 = max(0, (Q-(k-1))/C) if C > 0 else 0
        w2 = 1/(se**2 + t2)
        est = (w2*y).sum()/w2.sum(); s = np.sqrt(1/w2.sum())
    z = est/s
    return k, est, est-1.96*s, est+1.96*s, 2*(1-stats.norm.cdf(abs(z))), \
           max(0,(Q-(k-1))/Q)*100 if Q > 0 else 0

bad = 0; checked = 0
for _, r in sig[sig.stream == "CoRT"].iterrows():
    g = raw[(raw.comparison == r.comparison_name) &
            (raw.subgroup_category == r.subgroup) &
            (raw.outcome == r.outcome_name)]
    cont = r.outcome_name in CONT
    res = (iv if cont else mh)(arms(g, cont))
    if res is None:
        print("MISSING", r.comparison_name, r.outcome_name); bad += 1; continue
    k, est, lo, hi, p, i2 = res
    checked += 1
    ok = (k == int(r.n_studies) and abs(est-float(r.pooled_estimate)) < 5e-3
          and abs(p-float(r.p_effect)) < 1e-3 and abs(i2-float(r.I2_pct)) < 0.5)
    if not ok:
        bad += 1
        print(f"MISMATCH {r.comparison_name} | {r.subgroup} | {r.outcome_name}")
        print(f"   pipeline k={r.n_studies} est={r.pooled_estimate} p={r.p_effect} I2={r.I2_pct}")
        print(f"   check    k={k} est={est:.4f} p={p:.6f} I2={i2:.2f}")
print(f"\nindependently re-derived {checked} significant CoRT analyses, {bad} disagreements")
