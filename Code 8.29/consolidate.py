#!/usr/bin/env python3
"""Consolidate CoRT + LF + ID results into one results table and count them."""
import pandas as pd, numpy as np, os

def load(path, stream):
    d = pd.read_csv(path)
    d["stream"] = stream
    return d

cort = load("output/meta_analysis_summary.csv", "CoRT")
idd  = load("output_ID/meta_analysis_summary.csv", "ID")

# LF primary model = paired-correlation (the published model)
lfp = pd.read_csv("output_LF_paired_correlation/primary_pooled_results.csv")
lf = pd.DataFrame({
    "stream": "LF",
    "comparison_name": "LF Post vs Pre",
    "subgroup": lfp["Variant"].where(lfp["Variant"] != "primary", "primary"),
    "outcome_name": lfp["Pool"],
    "data_type": "continuous",
    "n_studies": lfp["k"], "total_patients": lfp["n_patients"],
    "pooled_estimate": lfp["MD"], "ci_lower": lfp["CI_lower"], "ci_upper": lfp["CI_upper"],
    "p_effect": lfp["p"], "I2_pct": lfp["I2"], "tau2": lfp["tau2"],
    "r_used": lfp["r"],
})

def is_primary(row):
    """Primary = the headline pooled analysis, not a sensitivity refit."""
    dt = str(row.get("data_type", ""))
    sg = str(row.get("subgroup", ""))
    if dt.startswith("LOO"):   # legacy rows; the pipeline no longer emits them
        return False
    if sg.startswith("SENSITIVITY") or "excl " in sg:
        return False
    return True

frames = []
for d in (cort, idd):
    d = d[d.apply(is_primary, axis=1)].copy()
    frames.append(d)
lf_primary = lf[lf["subgroup"] == "primary"].copy()
frames.append(lf_primary)

allr = pd.concat(frames, ignore_index=True, sort=False)
allr["p_num"] = pd.to_numeric(allr["p_effect"], errors="coerce")
pooled = allr[allr["p_num"].notna()].copy()          # k >= 2, actually estimated
notrun = allr[allr["p_num"].isna()].copy()           # k < 2 / not estimable

pooled["significant"] = pooled["p_num"] < 0.05

# ---- distinct (outcome, contributing study set) combinations ----
pooled["study_set"] = pooled.get("contributing_studies", pd.Series(dtype=str)).fillna("")
mask = pooled["study_set"] == ""
# LF/ID rows without the column: fall back to stream+outcome+subgroup identity
pooled.loc[mask, "study_set"] = (pooled.loc[mask, "stream"] + "|" +
                                 pooled.loc[mask, "outcome_name"].astype(str) + "|" +
                                 pooled.loc[mask, "subgroup"].astype(str))
pooled["combo"] = pooled["outcome_name"].astype(str) + " :: " + pooled["study_set"]

lines = []
def say(s=""):
    print(s); lines.append(s)

say("=" * 78)
say("ANALYSIS COUNTS — re-run of 2026-08-23")
say("=" * 78)
say()
say(f"{'stream':8}{'pooled (k>=2)':>16}{'significant':>14}{'nonsignificant':>16}{'not estimable':>16}")
for st in ("CoRT", "LF", "ID"):
    p = pooled[pooled.stream == st]
    n = notrun[notrun.stream == st]
    say(f"{st:8}{len(p):>16}{int(p.significant.sum()):>14}{int((~p.significant).sum()):>16}{len(n):>16}")
say(f"{'TOTAL':8}{len(pooled):>16}{int(pooled.significant.sum()):>14}"
    f"{int((~pooled.significant).sum()):>16}{len(notrun):>16}")
say()
say(f"Distinct (outcome x contributing-study-set) combinations: {pooled['combo'].nunique()}")
for st in ("CoRT", "LF", "ID"):
    p = pooled[pooled.stream == st]
    say(f"   {st}: {p['combo'].nunique()} distinct of {len(p)} reported")
say()
exp = 0.05 * pooled["combo"].nunique()
say(f"Expected false positives at alpha=0.05 across {pooled['combo'].nunique()} distinct "
    f"combinations: ~{exp:.0f}")
say(f"Observed significant: {int(pooled.significant.sum())} "
    f"({pooled[pooled.significant]['combo'].nunique()} distinct)")

cols = ["stream","comparison_name","subgroup","outcome_name","data_type","n_studies",
        "total_patients","pooled_estimate","ci_lower","ci_upper","p_effect","I2_pct",
        "tau2","pred_interval_lower","pred_interval_upper","contributing_studies",
        "excluded_double_zero","r_used"]
cols = [c for c in cols if c in pooled.columns]
pooled[cols].to_csv("results_all_pooled.csv", index=False)
pooled[pooled.significant][cols].to_csv("results_significant.csv", index=False)
pooled[~pooled.significant][cols].to_csv("results_nonsignificant.csv", index=False)
notrun_cols = [c for c in ["stream","comparison_name","subgroup","outcome_name",
                           "n_studies","reason_no_plot"] if c in notrun.columns]
notrun[notrun_cols].to_csv("results_not_estimable.csv", index=False)
open("analysis_counts.txt", "w").write("\n".join(lines) + "\n")
say()
say("wrote results_all_pooled.csv, results_significant.csv, "
    "results_nonsignificant.csv, results_not_estimable.csv, analysis_counts.txt")
