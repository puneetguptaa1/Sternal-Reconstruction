#!/usr/bin/env python3
"""
LF (Lung Function, pre vs post) and ID (Immediate vs Delayed reconstruction)
meta-analyses.

Reuses the exact statistical + plotting engine from meta_analysis_pipeline.py
(MH random-effects OR for dichotomous, IV random-effects MD for continuous,
DerSimonian-Laird tau2, +0.5 continuity correction, forest plots,
summary CSV).

For every outcome it emits, into output_LF/ or output_ID/:
  1. PRIMARY - all studies. No sensitivity analysis is run in either stream:
     the only exclusion anywhere in the review is the pre-specified clinical
     outlier (Zhao 2017) in the paired-correlation lung-function model.

Forest plots follow the pipeline convention: generated only when p < 0.05.
"""

import os
import openpyxl
import numpy as np
import pandas as pd

import meta_analysis_pipeline as mp

WORKBOOK = os.environ.get("MA_WORKBOOK", "master.xlsx")


def num(v):
    if v is None or v == "-" or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ──────────────────────────────────────────────────────────────────────
# Study builders
# ──────────────────────────────────────────────────────────────────────

def build_lf(rows, cols):
    """Continuous: comp1 = Post, comp2 = Pre  ->  MD = Post - Pre."""
    preM, preSD, postM, postSD = cols
    studies = []
    for r in rows:
        n = num(r[3]); pm = num(r[preM]); ps = num(r[preSD])
        qm = num(r[postM]); qs = num(r[postSD])
        if None in (n, pm, ps, qm, qs):
            continue
        studies.append({
            "study_id": int(r[0]), "study_name": f"{str(r[1]).strip()} {r[2]}",
            "comp1": {"n": int(n), "mean": qm, "sd": qs},   # Post
            "comp2": {"n": int(n), "mean": pm, "sd": ps},   # Pre
        })
    return studies


def build_id(rows, cols):
    """Dichotomous: comp1 = I (Immediate), comp2 = D (Delayed)."""
    ei, ed = cols
    studies = []
    for r in rows:
        nI = num(r[4]); nD = num(r[5]); xI = num(r[ei]); xD = num(r[ed])
        if None in (nI, nD, xI, xD):
            continue
        studies.append({
            "study_id": int(r[0]), "study_name": f"{str(r[1]).strip()} {r[2]}",
            "comp1": {"n": int(nI), "events": int(xI)},
            "comp2": {"n": int(nD), "events": int(xD)},
        })
    return studies


def build_id_continuous(rows, cols):
    """Continuous: comp1 = I (Immediate), comp2 = D (Delayed). I and D are
    different patients (unlike LF pre/post), so n(I) and n(D) are read
    separately rather than shared."""
    mI, sI, mD, sD = cols
    studies = []
    for r in rows:
        nI = num(r[4]); nD = num(r[5])
        mi = num(r[mI]); si = num(r[sI]); md = num(r[mD]); sd = num(r[sD])
        if None in (nI, nD, mi, si, md, sd):
            continue
        if si == 0 or sd == 0 or nI == 1 or nD == 1:
            continue
        studies.append({
            "study_id": int(r[0]), "study_name": f"{str(r[1]).strip()} {r[2]}",
            "comp1": {"n": int(nI), "mean": mi, "sd": si},
            "comp2": {"n": int(nD), "mean": md, "sd": sd},
        })
    return studies


# ──────────────────────────────────────────────────────────────────────
# Analysis helpers (thin wrappers over the shared engine)
# ──────────────────────────────────────────────────────────────────────

def analyse(studies, is_continuous):
    if is_continuous:
        return mp.run_iv_analysis(studies), studies
    classified = mp.classify_zero_events([dict(s) for s in studies])
    return mp.run_mh_analysis(classified), classified


def _study_list(result):
    import revman_naming as rn
    return "; ".join(sorted(rn.clean_study_label(x["study_name"]) for x in result["estimable"]))


def emit(result, comparison, role, outcome, c1, c2, is_continuous,
         out_dir, summary_rows, classified=None):
    mp.OUTPUT_DIR = out_dir
    p = result["p_effect"]
    is_sig = (not np.isnan(p)) and p < 0.05 and result["k"] >= 2

    plot_generated = False
    if is_sig:
        if not mp.NO_PLOTS:
            mp.make_forest_plot(result, comparison, role, outcome, c1, c2)
        plot_generated = True

    n_sz = n_dz = 0
    cc = False
    if not is_continuous and classified is not None:
        n_sz = sum(1 for s in classified if s.get("zero_status") == "single_zero")
        n_dz = sum(1 for s in classified if s.get("zero_status") == "double_zero")
        cc = n_sz > 0

    row = mp.make_summary_row(
        comparison, role, outcome, is_continuous,
        result=result, plot_generated=plot_generated,
        reason_no_plot="" if is_sig else "not significant",
        n_single_zero=n_sz, n_double_zero=n_dz, cc_applied=cc,
    )
    summary_rows.append(row)

    return is_sig


def status_row(comparison, role, outcome, is_continuous, msg, summary_rows):
    summary_rows.append(mp.make_summary_row(
        comparison, role, outcome, is_continuous, status=msg))


# ──────────────────────────────────────────────────────────────────────
# Per-dataset drivers
# ──────────────────────────────────────────────────────────────────────

def run_lf(rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # Named Post-first so the label order matches the arm order: comp1 = Post,
    # comp2 = Pre, and MD = Post - Pre.
    comparison, c1, c2 = "LF Post vs Pre", "Post", "Pre"
    # All seven measures reported in LF Raw Data. Absolute (L, ml/min) and
    # percent-predicted versions of the same measure are separate outcomes:
    # studies reported one or the other, and the two units cannot be pooled
    # together. A study reporting both contributes to both.
    outcomes = {
        "FEV1 (L)":      (4, 5, 6, 7),
        "FEV1%":         (8, 9, 10, 11),
        "FVC (L)":       (12, 13, 14, 15),
        "FVC%":          (16, 17, 18, 19),
        "FEV1_FVC":      (20, 21, 22, 23),
        "DLCO (ml/min)": (24, 25, 26, 27),
        "DLCO%":         (28, 29, 30, 31),
    }
    summary = []
    for name, cols in outcomes.items():
        studies = build_lf(rows, cols)
        result, _ = analyse(studies, True)
        if result is None or result["k"] < 2:
            status_row(comparison, "primary", name, True,
                       "NA - <2 studies", summary); continue
        sig = emit(result, comparison, "primary", name, c1, c2, True,
                   out_dir, summary, classified=studies)
        print(f"  LF {name:9s} primary: MD={result['MD_pooled']:+.2f} "
              f"p={result['p_effect']:.4f} I2={result['I2']:.0f}%  sig={sig}")
    pd.DataFrame(summary).to_csv(os.path.join(out_dir, "meta_analysis_summary.csv"),
                                 index=False)
    return summary


# Indication of each ID study, from the Organization sheet (2026-08-23).
# oncological = 0 studies and prophylactic = 1, so neither is estimable as a
# stratum; mixed-indication papers contribute to the pooled row only, per the
# analysis plan. Only "infection" is run as a subgroup.
ID_INDICATION = {
    "Cabbabe": "infection", "Hurtado-Sierra": "prophylactic", "Jacobs": "infection",
    "Kamel": "infection", "Onan": "mixed", "Piwnica-Worms": "infection",
    "Sears": "infection", "Yumun": "infection", "Zhou": "mixed",
}
ID_STRATA = [("primary", None), ("infection", "infection")]


def _stratum(studies, indication):
    if indication is None:
        return studies
    out = []
    for s in studies:
        ind = ID_INDICATION.get(str(s["study_name"]).rsplit(" ", 1)[0].strip())
        if ind is None:
            raise KeyError(f"run_id: study '{s['study_name']}' has no entry in "
                           f"ID_INDICATION. Add it explicitly - do not guess.")
        if ind == indication:
            out.append(s)
    return out


def run_id(rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    comparison, c1, c2 = "ID Immediate vs Delayed", "Immediate", "Delayed"
    # Complications was not a pre-specified outcome for the ID comparison and is
    # not analysed; the corresponding columns are absent from ID Raw Data.
    # All 7 outcome pairs present in ID Raw Data. LOS is continuous (MD); the
    # rest are dichotomous (OR). LOS was previously omitted along with
    # Seroma/hematoma and Necrosis - same class of bug as the missing LF
    # outcomes (#9 in the handoff): the outcome list was taken from the code,
    # not enumerated from the sheet.
    dichotomous_outcomes = {
        "Mortality":         (6, 7),
        "Reoperation":       (12, 13),
        "Infection":         (14, 15),
        "Dehiscence":        (16, 17),
        "Seroma/hematoma":   (18, 19),
        "Necrosis":          (20, 21),
    }
    continuous_outcomes = {
        "LOS (days)": (8, 9, 10, 11),
    }
    summary = []

    for name, cols in dichotomous_outcomes.items():
      all_studies = build_id(rows, cols)
      for role, indication in ID_STRATA:
        studies = _stratum(all_studies, indication)
        if len(studies) < 2:
            status_row(comparison, role, name, False,
                       f"NA - only {len(studies)} study/studies in stratum", summary); continue
        result, classified = analyse(studies, False)
        est = sum(1 for s in classified if s["zero_status"] != "double_zero")
        if result is None or est < 2:
            status_row(comparison, role, name, False,
                       f"NA - only {est} estimable study/studies", summary); continue
        sig = emit(result, comparison, role, name, c1, c2, False,
                   out_dir, summary, classified=classified)
        print(f"  ID {name:13s} {role:9s}: OR={result['OR_pooled']:.2f} "
              f"p={result['p_effect']:.4f} I2={result['I2']:.0f}%  sig={sig} k={result['k']}")
        if indication is not None:
            continue

    for name, cols in continuous_outcomes.items():
      all_studies = build_id_continuous(rows, cols)
      for role, indication in ID_STRATA:
        studies = _stratum(all_studies, indication)
        result, _ = analyse(studies, True) if len(studies) >= 2 else (None, None)
        if result is None or result["k"] < 2:
            status_row(comparison, role, name, True,
                       "NA - <2 studies", summary); continue
        sig = emit(result, comparison, role, name, c1, c2, True,
                   out_dir, summary, classified=studies)
        print(f"  ID {name:13s} {role:9s}: MD={result['MD_pooled']:+.2f} "
              f"p={result['p_effect']:.4f} I2={result['I2']:.0f}%  sig={sig} k={result['k']}")
        if indication is not None:
            continue

    pd.DataFrame(summary).to_csv(os.path.join(out_dir, "meta_analysis_summary.csv"),
                                 index=False)
    return summary


def main():
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    lf_rows = list(wb["LF Raw Data"].iter_rows(values_only=True))[1:]
    id_rows = list(wb["ID Raw Data"].iter_rows(values_only=True))[1:]
    wb.close()

    print("=== LF (Lung Function: Post vs Pre) -> output_LF/ ===")
    run_lf(lf_rows, "output_LF")
    print("\n=== ID (Immediate vs Delayed reconstruction) -> output_ID/ ===")
    run_id(id_rows, "output_ID")
    print("\nDone.")


if __name__ == "__main__":
    main()
