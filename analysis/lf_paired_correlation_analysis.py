#!/usr/bin/env python3
"""
LF (lung function, post vs pre) pooled analysis using literature-derived
within-patient pre/post correlations, applied per pool (outcome x unit) —
never a single global r, never carried across outcomes or units.

Each study's paired-difference variance is reconstructed from its reported
SD_pre and SD_post using the pool's correlation:

    SD_change_i = sqrt(SD_pre_i^2 + SD_post_i^2 - 2*r*SD_pre_i*SD_post_i)
    Var_i       = SD_change_i^2 / n_i

This differs from the primary (unpaired-equivalent, r=0) LF analysis reported
elsewhere in this project. That primary analysis is NOT changed by this
script — this is a standalone, literature-informed sensitivity/alternative
analysis. Pooling rule is unchanged from the primary pipeline: k=2 fixed
effect (inverse-variance), k>=3 DerSimonian-Laird random effects.

Does not modify meta_analysis_pipeline.py or run_lf_id_meta.py; reuses their
plotting/pooling code by shaping results into the same dict structure.

Run from the project root:  python3 lf_paired_correlation_analysis.py
"""

import os
import numpy as np
import pandas as pd
from scipy import stats
import openpyxl

import meta_analysis_pipeline as mp
import run_lf_id_meta as rli

WORKBOOK = os.environ.get("MA_WORKBOOK", "master.xlsx")
OUT_DIR = "output_LF_paired_correlation"
os.makedirs(OUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────
# 1. CORRELATIONS — one dictionary, edit here only.
#    Each pool = one outcome, one unit. Never shared across pools.
# ──────────────────────────────────────────────────────────────────────

# Column indices into LF Raw Data, matching run_lf_id_meta.build_lf's
# (preM, preSD, postM, postSD) convention.
LF_COLUMNS = {
    "FEV1 (L)":      (4, 5, 6, 7),
    "FEV1%":         (8, 9, 10, 11),
    "FVC (L)":       (12, 13, 14, 15),
    "FVC%":          (16, 17, 18, 19),
    "FEV1_FVC":      (20, 21, 22, 23),
    "DLCO (ml/min)": (24, 25, 26, 27),
    "DLCO%":         (28, 29, 30, 31),
}

# Primary point-estimate r per pool, as derived from the source studies.
PRIMARY_R = {
    "FEV1 (L)":      0.97,   # Meadows IPD 0.983 (n=6) + Huo 0.962 (n=12)
    "FEV1%":         0.74,   # Kohman grp 0.893 (n=7) + Kohman ctrl 0.652 (n=10) + Luezzi 0.729 (n=24). CI 0.55-0.86
    "FVC (L)":       0.98,   # Meadows IPD 0.984 (n=6) + Huo 0.988 (n=12)
    "FVC%":          0.65,   # Kohman grp 0.789 (n=7) + Kohman ctrl 0.533 (n=10). CI 0.18-0.88
    "FEV1_FVC":      0.63,   # Kohman x2 (0.369, 0.410) + Hayashi 0.736 (n=16) + Meadows 0.766 (n=6)
    "DLCO (ml/min)": 0.90,   # Meadows IPD 0.895 (n=5) - single source, CI 0.06-0.99
    "DLCO%":         0.70,   # IMPUTED - no study yields one; borrowed from % predicted spirometry pools
}

# 3-point sensitivity grids, pool-category-specific (not per outcome).
SENSITIVITY_GRIDS = {
    # Replaced 2026-08-03 with the user's final 4-point grids, one per
    # outcome (not shared by category), each derived directly from that
    # outcome's own 95% CI on the correlation (or, for DLCO%, its imputed
    # value). Point 1 = r=0 is the maximally conservative (independent-
    # samples-equivalent) case, included in every grid by design.
    "FEV1%":         [0.00, 0.50, 0.75, 0.90],   # CI 0.55-0.86
    "FVC%":          [0.00, 0.20, 0.65, 0.90],   # CI 0.18-0.88
    "FEV1_FVC":      [0.00, 0.30, 0.65, 0.85],   # CI 0.34-0.81
    "FEV1 (L)":      [0.00, 0.90, 0.97, 0.99],   # CI 0.91-0.99
    "FVC (L)":       [0.00, 0.90, 0.97, 0.99],   # CI 0.96-1.00
    "DLCO (ml/min)": [0.00, 0.30, 0.60, 0.90],   # CI 0.06-0.99
    "DLCO%":         [0.00, 0.30, 0.70, 0.90],   # imputed
}

# VC, % predicted (r=0.35, Hayashi IPD, n=16) is in the source table but is
# NOT run here: LF Raw Data has no VC column, only FEV1/FVC/FEV1:FVC/DLCO.
# Kept separate from FVC % predicted per instruction; simply not applicable.

# Zhao is a clinically pre-specified outlier/sensitivity exclusion for FEV1%
# and FVC% (pre-op FVC 39.2% vs 78.1-104.8% in all others, ~5.3 SD out; the
# only study where lung function *improved*) - established early in this
# project. This is a pre-specified outlier SENSITIVITY analysis, NOT a
# permanent inclusion-criteria exclusion like Kowalewski - the primary
# analysis for FEV1%/FVC% still includes Zhao. This exclusion is MANDATORY
# regardless of the resulting I2. There is no generic outlier rule; only
# fires when a single exclusion collapses I2 below 50%) because it rests on
# clinical justification, not a statistical threshold.
CLINICAL_OUTLIER_EXCLUSIONS = {"FEV1%": "Zhao 2017", "FVC%": "Zhao 2017"}
# matched with startswith(), so the appended indication label does not break it

# Blacher, Pechetov, Kowalewski were permanently excluded from the LF dataset
# (did not meet study inclusion criteria) as of 2026-07-31/08-06. As of the
# 2026-08-15 raw-data refresh, these three studies are physically absent from
# LF Raw Data (removed at the source, not filtered here) - the 8 remaining
# rows are Hayashi, Huo, Iarussi, Kohman, Luezzi, Meadows, Yong Bae, Zhao.
# This set is kept empty (rather than removed) so any future re-exclusion
# has an obvious place to go, and so load_lf_studies' filter step is a
# documented no-op rather than silently deleted logic.
EXCLUDE_STUDIES: set[str] = set()

FINE_SWEEP = np.round(np.arange(0.0, 1.0, 0.05), 2)  # r = 0.00 .. 0.95 step .05
FINE_SWEEP = np.append(FINE_SWEEP, 0.99)              # ... plus the ceiling

ALPHA = 0.05


# ──────────────────────────────────────────────────────────────────────
# 2. Per-study SD_change + admissibility check
# ──────────────────────────────────────────────────────────────────────

def sd_change_and_check(sd_pre, sd_post, r, study_name, pool_name):
    """Return SD_change, raising (not silently proceeding) on inadmissible input."""
    var_change = sd_pre**2 + sd_post**2 - 2 * r * sd_pre * sd_post
    if var_change < 0:
        raise ValueError(
            f"[{pool_name}] {study_name}: negative implied variance at r={r} "
            f"(SD_pre={sd_pre}, SD_post={sd_post}). Inputs inconsistent — halting."
        )
    sd_change = np.sqrt(var_change)
    lo = abs(sd_pre - sd_post)
    hi = sd_pre + sd_post
    admissible = (lo - 1e-9) <= sd_change <= (hi + 1e-9)
    if not admissible:
        raise ValueError(
            f"[{pool_name}] {study_name}: SD_change={sd_change:.4f} outside "
            f"admissible range [{lo:.4f}, {hi:.4f}] at r={r}. Halting."
        )
    return sd_change, admissible, lo, hi


# ──────────────────────────────────────────────────────────────────────
# 3. Pooling engine (paired variance), same shape as mp.run_iv_analysis
#    so the pipeline's own forest-plot code can be reused unmodified.
# ──────────────────────────────────────────────────────────────────────

def pool_paired(studies, r, pool_name):
    """studies: list of {"study_id","study_name","comp1":{n,mean,sd}(post),
    "comp2":{n,mean,sd}(pre)}. Returns a result dict shaped like
    mp.run_iv_analysis's output, plus a 'sd_change_rows' audit list."""
    k = len(studies)
    per_study = []
    MDs, SEs, ws_fixed = [], [], []
    sd_change_rows = []

    for s in studies:
        m_post, sd_post, n = s["comp1"]["mean"], s["comp1"]["sd"], s["comp1"]["n"]
        m_pre, sd_pre = s["comp2"]["mean"], s["comp2"]["sd"]

        sd_change, admissible, lo, hi = sd_change_and_check(
            sd_pre, sd_post, r, s["study_name"], pool_name)
        sd_change_rows.append({
            "pool": pool_name, "study": s["study_name"], "r": r,
            "sd_pre": sd_pre, "sd_post": sd_post, "n": n,
            "sd_change": round(sd_change, 4),
            "admissible_lo": round(lo, 4), "admissible_hi": round(hi, 4),
            "admissible": admissible,
        })

        MD_i = m_post - m_pre
        var_i = sd_change**2 / n
        SE_i = np.sqrt(var_i)
        w_i = 1.0 / SE_i**2 if SE_i > 0 else 0

        MDs.append(MD_i); SEs.append(SE_i); ws_fixed.append(w_i)
        per_study.append({"study": s, "MD": MD_i, "SE": SE_i, "w_fixed": w_i})

    MDs = np.array(MDs); SEs = np.array(SEs); ws = np.array(ws_fixed)

    MD_fixed = np.sum(ws * MDs) / np.sum(ws) if np.sum(ws) > 0 else np.nan
    Q_het = np.sum(ws * (MDs - MD_fixed) ** 2)
    df = k - 1

    if k == 2:
        tau2 = 0.0
        w_star = ws
        sum_w_star = np.sum(ws)
        MD_pooled = MD_fixed
        SE_pooled = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else np.nan
    else:
        C = np.sum(ws) - np.sum(ws**2) / np.sum(ws) if np.sum(ws) > 0 else 0
        tau2 = max(0, (Q_het - df) / C) if C > 0 else 0
        w_star = np.array([1.0 / (se**2 + tau2) if se > 0 else 0 for se in SEs])
        sum_w_star = np.sum(w_star)
        MD_pooled = np.sum(w_star * MDs) / sum_w_star if sum_w_star > 0 else np.nan
        SE_pooled = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else np.nan

    ci_lower = MD_pooled - 1.96 * SE_pooled if not np.isnan(MD_pooled) else np.nan
    ci_upper = MD_pooled + 1.96 * SE_pooled if not np.isnan(MD_pooled) else np.nan
    Z = MD_pooled / SE_pooled if SE_pooled > 0 else np.nan
    p_effect = 2 * (1 - stats.norm.cdf(abs(Z))) if not np.isnan(Z) else np.nan
    I2 = max(0, (Q_het - df) / Q_het) * 100 if Q_het > 0 and df > 0 else 0.0
    tau = np.sqrt(tau2)
    p_het = 1 - stats.chi2.cdf(Q_het, df) if df > 0 else np.nan

    if k >= 4:
        pi_lower, pi_upper = mp.compute_prediction_interval(
            MD_pooled, SE_pooled, tau2, k, log_scale=False)
    else:
        pi_lower, pi_upper = np.nan, np.nan

    weight_pcts = (w_star / sum_w_star * 100) if sum_w_star > 0 else np.zeros(k)
    for i, ps in enumerate(per_study):
        ps["ci_lower"] = MDs[i] - 1.96 * SEs[i]
        ps["ci_upper"] = MDs[i] + 1.96 * SEs[i]
        ps["weight_pct"] = weight_pcts[i]
        ps["w_star"] = w_star[i]

    # comp1 (post) and comp2 (pre) are the SAME patients measured twice, not
    # two separate arms - summing both would double-count every patient.
    total_patients = sum(s["comp1"]["n"] for s in studies)

    result = {
        "method": "IV", "k": k, "estimable": studies, "non_estimable": [],
        "per_study": per_study, "MD_pooled": MD_pooled, "SE_pooled": SE_pooled,
        "ci_lower": ci_lower, "ci_upper": ci_upper, "Z": Z, "p_effect": p_effect,
        "Q_het": Q_het, "df": df, "p_het": p_het, "I2": I2, "tau2": tau2, "tau": tau,
        "pi_lower": pi_lower, "pi_upper": pi_upper, "total_patients": total_patients,
        "pooled_estimate": MD_pooled, "pooled_log": np.nan, "r_used": r,
    }
    return result, sd_change_rows


# ──────────────────────────────────────────────────────────────────────
# 4. Load data
# ──────────────────────────────────────────────────────────────────────

# Surgical indication of each lung-function study, appended to the study label
# so every forest plot shows the case-mix it is pooling (the LF stream cannot be
# stratified by indication, so the label carries that information instead).
LF_INDICATION = {
    "Bae": "mixed", "Hayashi": "oncological", "Huo": "oncological",
    "Iarussi": "mixed", "Kohman": "infection", "Leuzzi": "oncological",
    "Meadows": "mixed", "Zhao": "mixed",
}


def _label_with_indication(name):
    surname = str(name).rsplit(" ", 1)[0].strip()
    ind = LF_INDICATION.get(surname)
    if ind is None:
        raise KeyError(f"LF_INDICATION has no entry for {name!r} - add it explicitly.")
    return f"{name}  ({ind})"


def load_lf_studies():
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    lf_rows = list(wb["LF Raw Data"].iter_rows(values_only=True))[1:]
    lf_rows = [r for r in lf_rows if r[1] not in EXCLUDE_STUDIES]
    wb.close()
    pools = {name: rli.build_lf(lf_rows, cols) for name, cols in LF_COLUMNS.items()}
    for studies in pools.values():
        for st in studies:
            st["study_name"] = _label_with_indication(st["study_name"])
    return pools


# ──────────────────────────────────────────────────────────────────────
# 5. Main
# ──────────────────────────────────────────────────────────────────────

def main():
    pools = load_lf_studies()

    all_sd_change_rows = []
    primary_rows = []
    grid_rows = []
    sweep_rows = []
    crossing_rows = []

    comparison, c1, c2 = "LF Post vs Pre (paired-correlation model)", "Post", "Pre"

    for pool_name, studies in pools.items():
        studies = [s for s in studies if len(studies) >= 2]  # no-op guard
        if len(studies) < 2:
            print(f"{pool_name}: <2 studies, skipped")
            continue
        r = PRIMARY_R[pool_name]

        # ---- primary, at this pool's literature-derived r ----
        result, sd_rows = pool_paired(studies, r, pool_name)
        all_sd_change_rows.extend(sd_rows)
        sig = result["p_effect"] < 0.05
        primary_rows.append({
            "Pool": pool_name, "Variant": "primary", "r": r, "k": result["k"],
            "n_patients": result["total_patients"],
            "MD": round(result["MD_pooled"], 4),
            "CI_lower": round(result["ci_lower"], 4), "CI_upper": round(result["ci_upper"], 4),
            "p": round(result["p_effect"], 4), "Q": round(result["Q_het"], 4),
            "tau2": round(result["tau2"], 4), "I2": round(result["I2"], 2),
                "PI_lower": (None if result["pi_lower"] != result["pi_lower"]
                             else round(result["pi_lower"], 4)),
                "PI_upper": (None if result["pi_upper"] != result["pi_upper"]
                             else round(result["pi_upper"], 4)),
            "significant": sig,
        })
        print(f"{pool_name:15s} r={r:.2f}  k={result['k']}  MD={result['MD_pooled']:+.3f}  "
              f"p={result['p_effect']:.4f}  I2={result['I2']:.1f}%  sig={sig}")

        if sig:
            mp.OUTPUT_DIR = OUT_DIR
            mp.make_forest_plot(result, comparison, f"primary (r={r})", pool_name, c1, c2)

        # ---- pre-specified clinical outlier exclusion ----
        # The only sensitivity analysis in the review: Zhao 2017 for FEV1%
        # and FVC%, pre-specified on baseline lung function. No exclusion is
        # ever triggered by heterogeneity.
        clinical_excl = CLINICAL_OUTLIER_EXCLUSIONS.get(pool_name)
        _names = [s["study_name"] for s in studies]
        oi = None
        if clinical_excl and any(n.startswith(clinical_excl) for n in _names):
            oi = next(i for i, n in enumerate(_names) if n.startswith(clinical_excl))
        if oi is not None:
            excl = studies[oi]["study_name"]
            sub = [s for j, s in enumerate(studies) if j != oi]
            sres, sd_rows2 = pool_paired(sub, r, pool_name)
            all_sd_change_rows.extend(sd_rows2)
            ssig = sres["p_effect"] < 0.05
            primary_rows.append({
                "Pool": pool_name, "Variant": f"excl {excl} (pre-specified outlier)", "r": r,
                "k": sres["k"], "n_patients": sres["total_patients"],
                "MD": round(sres["MD_pooled"], 4),
                "CI_lower": round(sres["ci_lower"], 4), "CI_upper": round(sres["ci_upper"], 4),
                "p": round(sres["p_effect"], 4), "Q": round(sres["Q_het"], 4),
                "tau2": round(sres["tau2"], 4), "I2": round(sres["I2"], 2),
                "PI_lower": (None if sres["pi_lower"] != sres["pi_lower"]
                             else round(sres["pi_lower"], 4)),
                "PI_upper": (None if sres["pi_upper"] != sres["pi_upper"]
                             else round(sres["pi_upper"], 4)),
                "significant": ssig,
            })
            print(f"   sensitivity excl {excl}: MD={sres['MD_pooled']:+.3f} "
                  f"p={sres['p_effect']:.4f} I2={sres['I2']:.1f}% sig={ssig}")
            if ssig:
                mp.OUTPUT_DIR = OUT_DIR
                mp.make_forest_plot(sres, comparison, f"excl {excl} (r={r})", pool_name, c1, c2)

        # ---- 3-point sensitivity grid (pool-specific) ----
        for r_grid in SENSITIVITY_GRIDS[pool_name]:
            gres, _ = pool_paired(studies, r_grid, pool_name)
            grid_rows.append({
                "Pool": pool_name, "r": r_grid, "k": gres["k"],
                "MD": round(gres["MD_pooled"], 4),
                "CI_lower": round(gres["ci_lower"], 4), "CI_upper": round(gres["ci_upper"], 4),
                "p": round(gres["p_effect"], 4), "tau2": round(gres["tau2"], 4),
                "I2": round(gres["I2"], 2),
                "significant": gres["p_effect"] < 0.05,
            })

        # ---- fine sweep r = 0.00 .. 0.99 step 0.05, find crossing points ----
        prev_sig = None
        crossings = []
        for r_fine in FINE_SWEEP:
            fres, _ = pool_paired(studies, float(r_fine), pool_name)
            sig_fine = fres["p_effect"] < ALPHA
            sweep_rows.append({
                "Pool": pool_name, "r": round(float(r_fine), 2), "k": fres["k"],
                "MD": round(fres["MD_pooled"], 4), "p": round(fres["p_effect"], 4),
                "significant": sig_fine,
            })
            if prev_sig is not None and sig_fine != prev_sig:
                crossings.append((round(float(r_fine), 2), prev_sig, sig_fine))
            prev_sig = sig_fine

        if crossings:
            for r_cross, was_sig, now_sig in crossings:
                direction = "loses significance" if was_sig and not now_sig else "gains significance"
                crossing_rows.append({
                    "Pool": pool_name, "crossing_r": r_cross, "direction": direction,
                })
        else:
            first_sig = sweep_rows[-len(FINE_SWEEP)]["significant"]
            status = "significant at every r in [0, 0.99]" if all(
                row["significant"] for row in sweep_rows[-len(FINE_SWEEP):]
            ) else "non-significant at every r in [0, 0.99]"
            crossing_rows.append({"Pool": pool_name, "crossing_r": None, "direction": status})

    # ---- write outputs ----
    pd.DataFrame(all_sd_change_rows).to_csv(f"{OUT_DIR}/sd_change_admissibility.csv", index=False)
    pd.DataFrame(primary_rows).to_csv(f"{OUT_DIR}/primary_pooled_results.csv", index=False)
    pd.DataFrame(grid_rows).to_csv(f"{OUT_DIR}/sensitivity_grid_3point.csv", index=False)
    pd.DataFrame(sweep_rows).to_csv(f"{OUT_DIR}/sensitivity_fine_sweep.csv", index=False)
    pd.DataFrame(crossing_rows).to_csv(f"{OUT_DIR}/significance_crossing_points.csv", index=False)

    print(f"\nAll outputs written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
