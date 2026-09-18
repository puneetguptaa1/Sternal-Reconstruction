#!/usr/bin/env python3
"""
Meta-Analysis Pipeline
Reads meta_analysis_data.csv, performs all statistical analyses,
produces RevMan-style forest plots and a summary CSV.
"""

import os
import re
import warnings

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")

from revman_forest_lib import revman_forest
import revman_naming as rn

warnings.filterwarnings("ignore", category=RuntimeWarning)

OUTPUT_DIR = os.environ.get("MA_OUTPUT_DIR", "output")
NO_PLOTS = os.environ.get("MA_NO_PLOTS") == "1"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CONTINUOUS_OUTCOMES = {"Op Time", "LOS"}

# Outcomes where a HIGHER value is the better result. The "Favors <arm>" captions
# on a forest plot assume the opposite (lower = better), which holds for every
# harm outcome here — mortality, infection, necrosis, reoperation, LOS, op time —
# but inverts for lung function. For these the two captions are swapped so the
# label matches the direction of benefit; the plotted effect is unchanged.
HIGHER_IS_BETTER_OUTCOMES = {
    "FEV1 (L)", "FEV1%", "FVC (L)", "FVC%", "FEV1_FVC", "DLCO (ml/min)", "DLCO%",
}


# NOTE: plot rendering is now delegated entirely to revman_forest_lib's
# revman_forest(); see rn.favors_labels() for the "Favours [X]" caption
# logic (RevMan house style, British spelling, used in place of the old
# favors_labels()/COLORS helpers that drove the removed raw-matplotlib
# drawing code).


# ──────────────────────────────────────────────────────────────────────
# 1.  DATA LOADING & GROUPING
# ──────────────────────────────────────────────────────────────────────

def load_data(path="meta_analysis_data.csv"):
    df = pd.read_csv(path, dtype={"sd": str, "val": str})
    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    df["sd"] = pd.to_numeric(df["sd"], errors="coerce")
    df["n"] = df["n"].astype(int)
    df["study_id"] = df["study_id"].astype(int)

    df["subgroup_label"] = df.apply(
        lambda r: "pooled" if str(r["analysis_type"]).startswith("MAIN") else r["subgroup_category"],
        axis=1,
    )
    return df


def group_analyses(df):
    """Return list of (comparison, subgroup_label, outcome) triples."""
    return list(df.groupby(["comparison", "subgroup_label", "outcome"]).groups.keys())


# ──────────────────────────────────────────────────────────────────────
# 2.  AGGREGATION
# ──────────────────────────────────────────────────────────────────────

def aggregate_arm(sub, is_continuous):
    """Aggregate sub-cohort rows for one (study_id, comp_arm) into a single arm record."""
    arm_n = sub["n"].sum()
    if is_continuous:
        ns = sub["n"].values.astype(float)
        means = sub["val"].values.astype(float)
        sds = sub["sd"].values

        if np.any(np.isnan(means)):
            return None  # missing mean → exclude
        if np.any(np.isnan(sds)):
            return None  # missing SD → exclude
        sds = sds.astype(float)

        arm_mean = np.sum(ns * means) / arm_n
        pooled_var = (np.sum(ns * sds**2) + np.sum(ns * (means - arm_mean) ** 2)) / arm_n
        arm_sd = np.sqrt(pooled_var)
        return {"n": int(arm_n), "mean": arm_mean, "sd": arm_sd}
    else:
        arm_events = sub["val"].sum()
        return {"n": int(arm_n), "events": int(arm_events)}


def aggregate_studies(df_group, is_continuous):
    """
    Aggregate all sub-cohorts into one row per (study_id, comp_arm).
    Returns a list of study dicts, each with comp1 and comp2 arm data,
    plus a list of excluded studies.
    """
    studies = {}
    excluded = []

    for (sid, sname), sdf in df_group.groupby(["study_id", "study_name"]):
        comp1_rows = sdf[sdf["comp_arm"] == "comp1"]
        comp2_rows = sdf[sdf["comp_arm"] == "comp2"]

        if comp1_rows.empty or comp2_rows.empty:
            continue

        arm1 = aggregate_arm(comp1_rows, is_continuous)
        arm2 = aggregate_arm(comp2_rows, is_continuous)

        if arm1 is None or arm2 is None:
            excluded.append({"study_id": sid, "study_name": sname, "reason": "Missing SD"})
            continue

        # Continuous only: an arm with SD = 0 or n = 1 carries no usable variance,
        # so the study cannot contribute a mean difference. Filtered here at the
        # data-aggregation step; the pooling estimators are untouched.
        if is_continuous:
            bad_arms = []
            for label, arm in (("comp1", arm1), ("comp2", arm2)):
                if arm["sd"] == 0:
                    bad_arms.append(f"{label} SD=0")
                if arm["n"] == 1:
                    bad_arms.append(f"{label} n=1")
            if bad_arms:
                excluded.append({"study_id": sid, "study_name": sname,
                                 "reason": "; ".join(bad_arms)})
                continue

        study = {"study_id": sid, "study_name": sname, "comp1": arm1, "comp2": arm2}
        studies[sid] = study

    return list(studies.values()), excluded


# ──────────────────────────────────────────────────────────────────────
# 3.  ZERO-EVENT CLASSIFICATION  (dichotomous only)
# ──────────────────────────────────────────────────────────────────────

def classify_zero_events(studies):
    """
    Classify each study as normal / single_zero / double_zero.
    Returns studies list with added 'zero_status' and 'footnote' fields.
    """
    for s in studies:
        e1 = s["comp1"]["events"]
        e2 = s["comp2"]["events"]
        # Non-event cells matter too: a table with an all-events arm (b or d = 0)
        # has an undefined ln(OR) and variance just as a zero-event arm does.
        ne1 = s["comp1"]["n"] - e1
        ne2 = s["comp2"]["n"] - e2
        if e1 == 0 and e2 == 0:
            # No events in either arm: contributes no information about the OR.
            s["zero_status"] = "double_zero"
            s["zero_detail"] = "no events in either arm"
            s["footnote"] = "‡"
        elif ne1 == 0 and ne2 == 0:
            # Every participant had the event in both arms. This is the exact
            # mirror image of the double-zero case (relabel event/non-event and
            # they swap) and is equally uninformative, so it is excluded on the
            # same rule rather than being carried in at OR = 1.
            s["zero_status"] = "double_zero"
            s["zero_detail"] = "all participants had the event in both arms"
            s["footnote"] = "‡"
        elif e1 == 0 or e2 == 0 or ne1 == 0 or ne2 == 0:
            # "single_zero" now means "any empty cell", so the 0.5 correction is
            # applied symmetrically: 0/10 vs 3/10 and 10/10 vs 7/10 both qualify.
            s["zero_status"] = "single_zero"
            s["zero_detail"] = "one empty cell; 0.5 continuity correction applied"
            s["footnote"] = "†"
        else:
            s["zero_status"] = "normal"
            s["zero_detail"] = ""
            s["footnote"] = ""
    return studies


def apply_continuity_correction(study):
    """Return corrected (a, b, c, d) with +0.5 for single-zero study."""
    a = study["comp1"]["events"] + 0.5
    b = study["comp1"]["n"] - study["comp1"]["events"] + 0.5
    c = study["comp2"]["events"] + 0.5
    d = study["comp2"]["n"] - study["comp2"]["events"] + 0.5
    return a, b, c, d


# ──────────────────────────────────────────────────────────────────────
# 4.  DICHOTOMOUS: MANTEL-HAENSZEL RANDOM EFFECTS
# ──────────────────────────────────────────────────────────────────────

def run_mh_analysis(studies):
    """
    Mantel-Haenszel OR with DerSimonian-Laird random effects.
    Returns result dict with pooled stats and per-study details.
    """
    estimable = [s for s in studies if s["zero_status"] != "double_zero"]
    non_estimable = [s for s in studies if s["zero_status"] == "double_zero"]
    k = len(estimable)

    if k == 0:
        return None

    per_study = []
    Rs, Ss = [], []
    ws_mh = []
    ws_iv = []
    log_ORs = []

    for s in estimable:
        if s["zero_status"] == "single_zero":
            a, b, c, d = apply_continuity_correction(s)
        else:
            a = s["comp1"]["events"]
            b = s["comp1"]["n"] - a
            c = s["comp2"]["events"]
            d = s["comp2"]["n"] - c

        n_total = a + b + c + d
        R = (a * d) / n_total
        S = (b * c) / n_total
        Rs.append(R)
        Ss.append(S)

        OR_i = R / S if S > 0 else np.nan
        log_OR_i = np.log(OR_i) if OR_i > 0 else np.nan
        w_i = R + S

        # Inverse-variance weight, 1 / var(ln OR_i). Used only for the
        # heterogeneity statistics (Q, tau2, I2), which require IV weights;
        # the Mantel-Haenszel weight w_i above still drives the MH estimate.
        var_log_OR_i = (1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d) if min(a, b, c, d) > 0 else np.nan
        w_iv_i = 1.0 / var_log_OR_i if var_log_OR_i > 0 else np.nan

        ws_mh.append(w_i)
        ws_iv.append(w_iv_i)
        log_ORs.append(log_OR_i)
        per_study.append({
            "study": s,
            "a": a, "b": b, "c": c, "d": d,
            "n_total": n_total, "R": R, "S": S,
            "OR": OR_i, "log_OR": log_OR_i, "w_mh": w_i, "w_iv": w_iv_i,
        })

    sum_R = np.sum(Rs)
    sum_S = np.sum(Ss)
    OR_MH = sum_R / sum_S if sum_S > 0 else np.nan
    log_OR_MH = np.log(OR_MH) if OR_MH > 0 else np.nan

    # Robins-Breslow-Greenland variance
    P_vals, Q_vals = [], []
    for ps in per_study:
        n_t = ps["n_total"]
        P_vals.append((ps["a"] + ps["d"]) / n_t)
        Q_vals.append((ps["b"] + ps["c"]) / n_t)

    term1 = np.sum([P * R for P, R in zip(P_vals, Rs)]) / (2 * sum_R**2)
    term2 = np.sum([P * S + Q * R for P, S, Q, R in zip(P_vals, Ss, Q_vals, Rs)]) / (2 * sum_R * sum_S)
    term3 = np.sum([Q * S for Q, S in zip(Q_vals, Ss)]) / (2 * sum_S**2)
    var_log_OR_MH = term1 + term2 + term3

    # Heterogeneity and pooling. Both now run on inverse-variance weights, so
    # there is no MH/IV hybrid: ws_mh drives only the MH point estimate (k = 2)
    # and the k = 2 forest-plot weight shares.
    ws = np.array(ws_mh)
    ws_het = np.array(ws_iv)          # 1 / var(ln OR_i)
    log_ors = np.array(log_ORs)

    # Q is centred on the inverse-variance fixed-effect estimate, as in standard DL.
    log_OR_IV = np.sum(ws_het * log_ors) / np.sum(ws_het) if np.sum(ws_het) > 0 else np.nan
    Q_het = np.sum(ws_het * (log_ors - log_OR_IV) ** 2)
    df = k - 1

    if k == 2:
        # Pre-specified: k = 2 is pooled fixed-effect Mantel-Haenszel. No tau2 is
        # estimated; the estimate and its variance come straight from OR_MH and
        # the Robins-Breslow-Greenland variance computed above.
        tau2 = 0.0
        w_star = ws
        sum_w_star = np.sum(ws)
        log_OR_RE = log_OR_MH
        SE_log_OR_RE = np.sqrt(var_log_OR_MH) if var_log_OR_MH > 0 else np.nan
    else:
        # k >= 3: standard inverse-variance DerSimonian-Laird random effects.
        C = np.sum(ws_het) - np.sum(ws_het**2) / np.sum(ws_het) if np.sum(ws_het) > 0 else 0
        tau2 = max(0, (Q_het - df) / C) if C > 0 else 0

        # Random-effects weights 1 / (var_i + tau2), built from the IV weights
        w_star = np.array([1.0 / (1.0 / w + tau2) if w > 0 else 0 for w in ws_het])
        sum_w_star = np.sum(w_star)

        log_OR_RE = np.sum(w_star * log_ors) / sum_w_star if sum_w_star > 0 else np.nan
        SE_log_OR_RE = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else np.nan
    OR_pooled = np.exp(log_OR_RE) if not np.isnan(log_OR_RE) else np.nan
    ci_lower = np.exp(log_OR_RE - 1.96 * SE_log_OR_RE) if not np.isnan(log_OR_RE) else np.nan
    ci_upper = np.exp(log_OR_RE + 1.96 * SE_log_OR_RE) if not np.isnan(log_OR_RE) else np.nan

    # Test of overall effect
    Z = log_OR_RE / SE_log_OR_RE if SE_log_OR_RE > 0 else np.nan
    p_effect = 2 * (1 - stats.norm.cdf(abs(Z))) if not np.isnan(Z) else np.nan

    # Heterogeneity. Q is undefined when any contributing study still has an empty
    # cell after the continuity-correction rule has been applied (a study with zero
    # NON-events is classified "normal" and so is never corrected), which makes its
    # inverse-variance weight undefined. Report that as NaN rather than as I2 = 0.
    if np.isnan(Q_het):
        I2 = np.nan
    else:
        I2 = max(0, (Q_het - df) / Q_het) * 100 if Q_het > 0 and df > 0 else 0
    tau = np.sqrt(tau2)
    p_het = 1 - stats.chi2.cdf(Q_het, df) if df > 0 else np.nan

    # Prediction interval — not meaningful at k = 2 (fixed-effect, no tau2)
    if k == 2:
        pi_lower, pi_upper = np.nan, np.nan
    else:
        pi_lower, pi_upper = compute_prediction_interval(
            log_OR_RE, SE_log_OR_RE, tau2, k, log_scale=True
        )

    # Per-study CI on OR scale
    weight_pcts = (w_star / sum_w_star * 100) if sum_w_star > 0 else np.zeros(k)
    for i, ps in enumerate(per_study):
        # SE of ln(OR_i) is sqrt(var_i) = sqrt(1/w_iv_i); the MH weight is not a
        # variance and must not be used here.
        se_i = np.sqrt(1.0 / ws_het[i]) if ws_het[i] > 0 else np.nan
        ps["OR_ci_lower"] = np.exp(log_ors[i] - 1.96 * se_i) if not np.isnan(se_i) else np.nan
        ps["OR_ci_upper"] = np.exp(log_ors[i] + 1.96 * se_i) if not np.isnan(se_i) else np.nan
        ps["weight_pct"] = weight_pcts[i]
        ps["w_star"] = w_star[i]

    total_patients = sum(
        s["comp1"]["n"] + s["comp2"]["n"] for s in estimable
    )

    return {
        "method": "MH",
        "k": k,
        "estimable": estimable,
        "non_estimable": non_estimable,
        "per_study": per_study,
        "OR_MH": OR_MH,
        "OR_pooled": OR_pooled,
        "log_OR_RE": log_OR_RE,
        "SE_log_OR_RE": SE_log_OR_RE,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "Z": Z,
        "p_effect": p_effect,
        "Q_het": Q_het,
        "df": df,
        "p_het": p_het,
        "I2": I2,
        "tau2": tau2,
        "tau": tau,
        "pi_lower": pi_lower,
        "pi_upper": pi_upper,
        "total_patients": total_patients,
        "pooled_estimate": OR_pooled,
        "pooled_log": log_OR_RE,
    }


# ──────────────────────────────────────────────────────────────────────
# 5.  CONTINUOUS: INVERSE-VARIANCE RANDOM EFFECTS
# ──────────────────────────────────────────────────────────────────────

def run_iv_analysis(studies):
    """
    Inverse-variance weighted mean difference with DL random effects.
    """
    k = len(studies)
    if k == 0:
        return None

    per_study = []
    MDs, SEs, ws_fixed = [], [], []

    for s in studies:
        m1 = s["comp1"]["mean"]
        m2 = s["comp2"]["mean"]
        sd1 = s["comp1"]["sd"]
        sd2 = s["comp2"]["sd"]
        n1 = s["comp1"]["n"]
        n2 = s["comp2"]["n"]

        MD_i = m1 - m2
        SE_i = np.sqrt(sd1**2 / n1 + sd2**2 / n2) if n1 > 0 and n2 > 0 else np.nan
        w_i = 1.0 / SE_i**2 if SE_i > 0 else 0

        MDs.append(MD_i)
        SEs.append(SE_i)
        ws_fixed.append(w_i)
        per_study.append({"study": s, "MD": MD_i, "SE": SE_i, "w_fixed": w_i})

    MDs = np.array(MDs)
    SEs = np.array(SEs)
    ws = np.array(ws_fixed)

    # Fixed-effect pooled MD
    MD_fixed = np.sum(ws * MDs) / np.sum(ws) if np.sum(ws) > 0 else np.nan

    # DerSimonian-Laird tau²
    Q_het = np.sum(ws * (MDs - MD_fixed) ** 2)
    df = k - 1

    if k == 2:
        # Pre-specified: k = 2 is pooled fixed-effect inverse-variance, no tau2.
        tau2 = 0.0
        w_star = ws
        sum_w_star = np.sum(ws)
        MD_pooled = MD_fixed
        SE_pooled = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else np.nan
    else:
        C = np.sum(ws) - np.sum(ws**2) / np.sum(ws) if np.sum(ws) > 0 else 0
        tau2 = max(0, (Q_het - df) / C) if C > 0 else 0

        # Random-effects weights
        w_star = np.array([1.0 / (se**2 + tau2) if se > 0 else 0 for se in SEs])
        sum_w_star = np.sum(w_star)

        MD_pooled = np.sum(w_star * MDs) / sum_w_star if sum_w_star > 0 else np.nan
        SE_pooled = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else np.nan
    ci_lower = MD_pooled - 1.96 * SE_pooled if not np.isnan(MD_pooled) else np.nan
    ci_upper = MD_pooled + 1.96 * SE_pooled if not np.isnan(MD_pooled) else np.nan

    Z = MD_pooled / SE_pooled if SE_pooled > 0 else np.nan
    p_effect = 2 * (1 - stats.norm.cdf(abs(Z))) if not np.isnan(Z) else np.nan

    I2 = max(0, (Q_het - df) / Q_het) * 100 if Q_het > 0 and df > 0 else 0
    tau = np.sqrt(tau2)
    p_het = 1 - stats.chi2.cdf(Q_het, df) if df > 0 else np.nan

    # Prediction interval — not meaningful at k = 2 (fixed-effect, no tau2)
    if k == 2:
        pi_lower, pi_upper = np.nan, np.nan
    else:
        pi_lower, pi_upper = compute_prediction_interval(
            MD_pooled, SE_pooled, tau2, k, log_scale=False
        )

    weight_pcts = (w_star / sum_w_star * 100) if sum_w_star > 0 else np.zeros(k)
    for i, ps in enumerate(per_study):
        ps["ci_lower"] = MDs[i] - 1.96 * SEs[i]
        ps["ci_upper"] = MDs[i] + 1.96 * SEs[i]
        ps["weight_pct"] = weight_pcts[i]
        ps["w_star"] = w_star[i]

    total_patients = sum(s["comp1"]["n"] + s["comp2"]["n"] for s in studies)

    return {
        "method": "IV",
        "k": k,
        "estimable": studies,
        "non_estimable": [],
        "per_study": per_study,
        "MD_pooled": MD_pooled,
        "SE_pooled": SE_pooled,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "Z": Z,
        "p_effect": p_effect,
        "Q_het": Q_het,
        "df": df,
        "p_het": p_het,
        "I2": I2,
        "tau2": tau2,
        "tau": tau,
        "pi_lower": pi_lower,
        "pi_upper": pi_upper,
        "total_patients": total_patients,
        "pooled_estimate": MD_pooled,
    }


# ──────────────────────────────────────────────────────────────────────
# 6.  COMMON STATISTICS
# ──────────────────────────────────────────────────────────────────────

def i2_category(i2_val):
    if i2_val < 25:
        return "low"
    elif i2_val <= 50:
        return "moderate"
    elif i2_val <= 75:
        return "high"
    else:
        return "very high"


def compute_prediction_interval(pooled, se_pooled, tau2, k, log_scale=False):
    """Compute 95% prediction interval."""
    # Higgins-Thompson-Spiegelhalter: mu +/- t(0.975, k-2) * sqrt(tau2 + SE^2).
    #
    # Reported only for k >= 4. At k = 3 the t distribution has a single degree of
    # freedom (t(0.975, df=1) = 12.71), which produces intervals spanning several
    # orders of magnitude and carrying no usable information; at k = 2 no degrees
    # of freedom remain at all. The interval is well defined at k = 3 but is not
    # interpretable, so it is suppressed rather than shown.
    if k < 4 or np.isnan(pooled) or np.isnan(se_pooled):
        return np.nan, np.nan

    spread = np.sqrt(tau2 + se_pooled**2)
    t_crit = stats.t.ppf(0.975, df=k - 2)

    pi_lower = pooled - t_crit * spread
    pi_upper = pooled + t_crit * spread

    if log_scale:
        pi_lower = np.exp(pi_lower)
        pi_upper = np.exp(pi_upper)

    return pi_lower, pi_upper


# ──────────────────────────────────────────────────────────────────────
# 7.  FOREST PLOT
# ──────────────────────────────────────────────────────────────────────

def sanitize_filename(s):
    s = s.replace(" ", "_")
    s = re.sub(r"[^\w\-_.]", "", s)
    return s


def _revman_rows_from_result(result, is_dich):
    """
    Build the `rows` list (per Appendix A of the handoff doc) plus pooled
    totals and footnotes, from a run_mh_analysis()/run_iv_analysis() result
    dict, shared by every forest plot.
    """
    rows = []
    for ps in result["per_study"]:
        s = ps["study"]
        label = rn.clean_study_label(s["study_name"])
        footnote = f" {s['footnote']}" if s.get("footnote") else None
        if is_dich:
            rows.append(dict(
                name=label, footnote=footnote,
                eA=int(s["comp1"]["events"]), nA=s["comp1"]["n"],
                eB=int(s["comp2"]["events"]), nB=s["comp2"]["n"],
                weight=ps["weight_pct"], est=ps["OR"],
                lo=ps["OR_ci_lower"], hi=ps["OR_ci_upper"],
            ))
        else:
            rows.append(dict(
                name=label, footnote=footnote,
                mA=s["comp1"]["mean"], sA=s["comp1"]["sd"], nA=s["comp1"]["n"],
                mB=s["comp2"]["mean"], sB=s["comp2"]["sd"], nB=s["comp2"]["n"],
                weight=ps["weight_pct"], est=ps["MD"],
                lo=ps["ci_lower"], hi=ps["ci_upper"],
            ))

    for s in result["non_estimable"]:
        label = rn.clean_study_label(s["study_name"])
        rows.append(dict(
            name=label, footnote=" ‡",
            eA=int(s["comp1"]["events"]), nA=s["comp1"]["n"],
            eB=int(s["comp2"]["events"]), nB=s["comp2"]["n"],
            excluded=True,
        ))

    all_studies = result["estimable"] + result["non_estimable"]
    total_nA = sum(s["comp1"]["n"] for s in all_studies)
    total_nB = sum(s["comp2"]["n"] for s in all_studies)

    if is_dich:
        total_est, total_lo, total_hi = result["OR_pooled"], result["ci_lower"], result["ci_upper"]
    else:
        total_est, total_lo, total_hi = result["MD_pooled"], result["ci_lower"], result["ci_upper"]

    het_lines = [
        rn.build_heterogeneity_line(result["tau2"], result["Q_het"], result["df"],
                                     result["p_het"], result["I2"]),
        rn.build_overall_effect_line(result["Z"], result["p_effect"]),
    ]
    pi_lo, pi_hi = result["pi_lower"], result["pi_upper"]
    if not np.isnan(pi_lo) and not np.isnan(pi_hi):
        het_lines.append(rn.build_prediction_interval_line(pi_lo, pi_hi))

    footnotes = []
    has_single_zero = any(
        ps["study"].get("zero_status") == "single_zero" for ps in result["per_study"]
    )
    if has_single_zero:
        footnotes.append(rn.FOOTNOTE_SINGLE_ZERO)
    if result["non_estimable"]:
        footnotes.append(rn.FOOTNOTE_DOUBLE_ZERO)

    return rows, total_est, total_lo, total_hi, total_nA, total_nB, het_lines, footnotes


def _render_revman_forest(result, comparison, subgroup_label, outcome,
                          comp1_name, comp2_name, out_tag, excluding_study=None):
    """Build a RevMan-house-style forest plot via revman_forest_lib and
    save it (PNG + PDF) into OUTPUT_DIR. Returns the PNG path."""
    is_dich = result["method"] == "MH"
    data_type = "binary" if is_dich else "continuous"

    rows, total_est, total_lo, total_hi, total_nA, total_nB, het_lines, footnotes = \
        _revman_rows_from_result(result, is_dich)

    exception_key = rn.model_exception_key_for(comparison, outcome, subgroup_label, excluding_study)
    model, method_name, effect_name = rn.select_model(result["k"], data_type, exception_key=exception_key)

    groupA_disp = rn.format_group_name(comp1_name)
    groupB_disp = rn.format_group_name(comp2_name)

    title = rn.title_bar_text(comparison, outcome, subgroup_label,
                              excluding_study=excluding_study)

    favors_left, favors_right = rn.favors_labels(
        outcome, HIGHER_IS_BETTER_OUTCOMES, groupA_disp, groupB_disp
    )

    all_lo = [r["lo"] for r in rows if not r.get("excluded")] + [total_lo]
    all_hi = [r["hi"] for r in rows if not r.get("excluded")] + [total_hi]
    xlim, xticks = rn.pick_axis_range(all_lo, all_hi, log_scale=is_dich)

    fname = sanitize_filename(f"{comparison}_{subgroup_label}_{outcome}_{out_tag}")
    out_png = os.path.join(OUTPUT_DIR, fname + ".png")
    out_pdf = os.path.join(OUTPUT_DIR, fname + ".pdf")

    revman_forest(
        title_bar_text=title,
        data_type=data_type,
        groupA_name=groupA_disp, groupB_name=groupB_disp,
        effect_name=effect_name, method_name=method_name,
        rows=rows,
        total_est=total_est, total_lo=total_lo, total_hi=total_hi,
        total_nA=total_nA, total_nB=total_nB,
        het_lines=het_lines, footnotes=footnotes,
        xlim=xlim, xticks=xticks,
        favors_left=favors_left, favors_right=favors_right,
        log_scale=is_dich,
        out_png=out_png, out_pdf=out_pdf,
    )
    return out_png


def make_forest_plot(result, comparison, subgroup_label, outcome, comp1_name, comp2_name):
    """Generate the main RevMan-house-style forest plot."""
    return _render_revman_forest(result, comparison, subgroup_label, outcome,
                                 comp1_name, comp2_name, out_tag="forest")


# ──────────────────────────────────────────────────────────────────────
# 8.  MAIN PIPELINE
# ──────────────────────────────────────────────────────────────────────

def run_pipeline():
    print("Loading data...")
    df = load_data()
    analysis_keys = group_analyses(df)
    print(f"Found {len(analysis_keys)} unique analysis groups.")

    summary_rows = []

    for comparison, subgroup_label, outcome in sorted(analysis_keys):
        tag = f"{comparison} | {subgroup_label} | {outcome}"
        is_continuous = outcome in CONTINUOUS_OUTCOMES

        mask = (
            (df["comparison"] == comparison)
            & (df["subgroup_label"] == subgroup_label)
            & (df["outcome"] == outcome)
        )
        df_group = df[mask]

        comp1_name = df_group["comp1"].iloc[0]
        comp2_name = df_group["comp2"].iloc[0]

        studies, excluded = aggregate_studies(df_group, is_continuous)

        # ── Special case: no studies ──
        if len(studies) == 0:
            print(f"  [{tag}] No studies available.")
            summary_rows.append(make_summary_row(
                comparison, subgroup_label, outcome, is_continuous,
                status="NA – No studies available",
            ))
            continue

        # ── Dichotomous: classify zero events ──
        if not is_continuous:
            studies = classify_zero_events(studies)

        # Count estimable
        if is_continuous:
            estimable_count = len(studies)
        else:
            estimable_count = sum(1 for s in studies if s["zero_status"] != "double_zero")

        # ── Special case: single study ──
        if len(studies) == 1 or estimable_count < 2:
            actual_studies = len(studies)
            if is_continuous and excluded:
                dropped = "; ".join(f"{e['study_name']} ({e['reason']})" for e in excluded)
                reason = ("Reported descriptively only – fewer than 2 usable studies "
                          f"after excluding {dropped}")
            elif actual_studies == 1:
                reason = "NA – Only 1 study; meta-analysis not performed"
            else:
                reason = f"NA – Only {estimable_count} estimable study/studies"
            print(f"  [{tag}] {reason}")
            summary_rows.append(make_summary_row(
                comparison, subgroup_label, outcome, is_continuous,
                status=reason,
                n_studies=actual_studies,
                studies=studies,
            ))
            continue

        # ── Run main analysis ──
        if is_continuous:
            result = run_iv_analysis(studies)
        else:
            result = run_mh_analysis(studies)

        if result is None:
            summary_rows.append(make_summary_row(
                comparison, subgroup_label, outcome, is_continuous,
                status="NA – Analysis failed",
            ))
            continue

        # Count zero-event studies
        n_single_zero = sum(1 for s in studies if not is_continuous and s.get("zero_status") == "single_zero")
        n_double_zero = sum(1 for s in studies if not is_continuous and s.get("zero_status") == "double_zero")
        cc_applied = n_single_zero > 0

        # ── Main forest plot (only if p < 0.05) ──
        plot_generated = False
        reason_no_plot = ""
        p_eff = result["p_effect"]
        is_sig = (not np.isnan(p_eff)) and p_eff < 0.05
        if is_sig and result["k"] >= 2 and not NO_PLOTS:
            plot_path = make_forest_plot(result, comparison, subgroup_label, outcome,
                                         comp1_name, comp2_name)
            plot_generated = True
            print(f"  [{tag}] p={p_eff:.4f} — forest plot saved: {plot_path}")
        else:
            reason_no_plot = "not significant"
            p_str = f"{p_eff:.4f}" if not np.isnan(p_eff) else "nan"
            print(f"  [{tag}] p={p_str} — no main plot ({reason_no_plot})")

        # ── Summary row ──
        summary_rows.append(make_summary_row(
            comparison, subgroup_label, outcome, is_continuous,
            result=result,
            plot_generated=plot_generated,
            reason_no_plot=reason_no_plot,
            n_single_zero=n_single_zero,
            n_double_zero=n_double_zero,
            cc_applied=cc_applied,
        ))


    # Write summary CSV
    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(OUTPUT_DIR, "meta_analysis_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSummary CSV saved: {summary_path}")
    print(f"Total rows in summary: {len(summary_rows)}")


# ──────────────────────────────────────────────────────────────────────
# 9.  SUMMARY CSV HELPERS
# ──────────────────────────────────────────────────────────────────────

def make_summary_row(comparison, subgroup_label, outcome, is_continuous,
                     status=None, result=None, plot_generated=False,
                     reason_no_plot="", n_studies=0, studies=None,
                     n_single_zero=0, n_double_zero=0, cc_applied=False):
    row = {
        "comparison_name": comparison,
        "subgroup": subgroup_label,
        "outcome_name": outcome,
        "data_type": "continuous" if is_continuous else "dichotomous",
    }

    if status:
        row.update({
            "n_studies": n_studies,
            "total_patients": "",
            "pooled_estimate": "",
            "ci_lower": "",
            "ci_upper": "",
            "z_stat": "",
            "p_effect": "",
            "cochran_Q": "",
            "p_het": "",
            "I2_pct": "",
            "I2_category": "",
            "tau2": "",
            "tau": "",
            "pred_interval_lower": "",
            "pred_interval_upper": "",
            "plot_generated": False,
            "reason_no_plot": status,
            "n_zero_one_arm": 0,
            "n_double_zero": 0,
            "continuity_correction_applied": False,
        })
        return row

    r = result
    row.update({
        "contributing_studies": "; ".join(
            sorted(rn.clean_study_label(x["study_name"]) for x in r["estimable"])),
        "excluded_double_zero": "; ".join(
            sorted(rn.clean_study_label(x["study_name"]) for x in r["non_estimable"])),
        "n_studies": r["k"],
        "total_patients": r["total_patients"],
        "pooled_estimate": round(r["pooled_estimate"], 4),
        "ci_lower": round(r["ci_lower"], 4),
        "ci_upper": round(r["ci_upper"], 4),
        "z_stat": round(r["Z"], 4) if not np.isnan(r["Z"]) else "",
        "p_effect": round(r["p_effect"], 6) if not np.isnan(r["p_effect"]) else "",
        "cochran_Q": round(r["Q_het"], 4),
        "p_het": round(r["p_het"], 6) if not np.isnan(r["p_het"]) else "",
        "I2_pct": round(r["I2"], 2),
        "I2_category": i2_category(r["I2"]),
        "tau2": round(r["tau2"], 4),
        "tau": round(r["tau"], 4),
        "pred_interval_lower": round(r["pi_lower"], 4) if not np.isnan(r["pi_lower"]) else "",
        "pred_interval_upper": round(r["pi_upper"], 4) if not np.isnan(r["pi_upper"]) else "",
        "plot_generated": plot_generated,
        "reason_no_plot": reason_no_plot,
        "n_zero_one_arm": n_single_zero,
        "n_double_zero": n_double_zero,
        "continuity_correction_applied": cc_applied,
    })
    return row




if __name__ == "__main__":
    run_pipeline()
