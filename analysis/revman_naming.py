"""
revman_naming.py — naming, model-selection, and statistics-text rules for the
RevMan 2020 house style, per FOREST_PLOT_HANDOFF.md.

This module intentionally does NOT try to algorithmically infer study-label
cleanup, title wording, or model-selection exceptions from scratch. Per the
handoff doc, a prior naive regex-based cleanup silently corrupted 11 study
labels, and there are hand-approved exceptions to the k-based Fixed/Random
rule. So: known mappings are seeded here explicitly, and anything unmapped
raises loudly instead of being guessed.
"""

import re

MINUS = "−"  # proper minus sign, U+2212


# ──────────────────────────────────────────────────────────────────────
# 1. Study label cleanup (handoff §2.1)
# ──────────────────────────────────────────────────────────────────────

# Seeded from the "Known year mappings" table in handoff §2.1. Keyed by the
# raw study-name string as it may appear in a pipeline's data source (bare
# surname, or "Author et al" with no year). Add to this as new bare-surname
# / no-year studies are found — never guess a year.
STUDY_LABEL_OVERRIDES = {
    "Yong Bae": "Bae 2024",
    "Blacher": "Blacher 1996",
    "Cabbabe": "Cabbabe 2008",
    "Jacobs": "Jacobs 2008",
    "Kamel": "Kamel 2019",
    "Kohman": "Kohman 1991",
    "Luezzi": "Luezzi 2014",
    "Meadows": "Meadows 1985",
    "Piwnica-Worms": "Piwnica-Worms 2020",
    "Sears": "Sears 2017",
    "Zhou": "Zhou 2019",
    "Huo": "Huo 2025",
    "Iarussi": "Iarussi 2010",
    # LF/ID-pipeline-specific studies, years confirmed against the delivered
    # archive (revman_forest_plots_20260815/) and/or example_usage.py — the
    # same "verify, don't guess" standard as the table above.
    "Zhao": "Zhao 2017",                    # confirmed: handoff §9, example_usage.py
    "Hurtado-Sierra": "Hurtado-Sierra 2018",  # confirmed: ID_Mortality_primary.png
    "Onan": "Onan 2018",                      # confirmed: ID_Mortality_primary.png
    "Yumun": "Yumun 2014",                    # confirmed: ID_Mortality_primary.png
    # NOTE: "Hayashi" (appears in LF Raw Data, e.g. the FEV1_FVC pool) has NO
    # confirmed year anywhere in this repo (not in the handoff doc, the
    # archive, example_usage.py, or any script comment/CSV). Deliberately
    # left unmapped — clean_study_label will raise loudly if a plot ever
    # needs it. Do not add a guessed year.
}

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_ET_AL_RE = re.compile(r"\s*et\s+al\.?\s*", re.IGNORECASE)


def clean_study_label(raw_name):
    """
    Author surname + year only, per handoff §2.1.

    - Strips "et al"/"et al." entirely.
    - Applies STUDY_LABEL_OVERRIDES (checked against both the raw string and
      the et-al-stripped string).
    - Collapses stray internal whitespace (e.g. "Cole  2022" -> "Cole 2022")
      but otherwise preserves the string as-is, including hyphenated names.
    - Raises loudly if the resulting label has no year and no override on
      file — never silently guesses a year. This is the exact failure mode
      the handoff doc calls out as having once silently dropped years from
      eleven studies.
    """
    if raw_name is None:
        raise ValueError("clean_study_label: got None")

    raw_stripped = raw_name.strip()
    if raw_stripped in STUDY_LABEL_OVERRIDES:
        return STUDY_LABEL_OVERRIDES[raw_stripped]

    cleaned = _ET_AL_RE.sub(" ", raw_stripped).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if cleaned in STUDY_LABEL_OVERRIDES:
        return STUDY_LABEL_OVERRIDES[cleaned]

    if _YEAR_RE.search(cleaned):
        return cleaned

    raise ValueError(
        f"clean_study_label: '{raw_name}' has no year and no entry in "
        f"STUDY_LABEL_OVERRIDES. Add an explicit mapping — do not guess a "
        f"year. (This is the exact defect the handoff doc warns about: an "
        f"'et al' cleanup once silently dropped years from eleven studies.)"
    )


# ──────────────────────────────────────────────────────────────────────
# 2. Comparison / group-name formatting (handoff §2.2)
# ──────────────────────────────────────────────────────────────────────

# A leading token like "pPM", "pGO", "pLD" is a technical abbreviation and
# must keep its casing even at the start of a title or column header —
# overriding the "capitalize the first letter" rule.
_TECH_ABBREV_START_RE = re.compile(r"^p[A-Z]")


def _capitalize_first_unless_abbrev(s):
    if not s:
        return s
    if _TECH_ABBREV_START_RE.match(s):
        return s
    return s[0].upper() + s[1:]


# Fixed, verified overrides for comparison strings that need more than the
# generic "capitalize first letter + v->vs" rule to reach their approved
# display form. Confirmed against revman_forest_plots_20260815/ (the
# LF_*_primary_r*.png / LF_*_LOO*.png titles all read
# "LF Post vs Pre (Paired-Correlation Model)").
COMPARISON_TITLE_OVERRIDES = {
    "LF Post vs Pre (paired-correlation model)": "LF Post vs Pre (Paired-Correlation Model)",
}

# The literal comparison string run_lf_id_meta.py's run_id() uses. Per
# handoff §2.2, ID plots are the documented exception: the comparison text
# is just "ID" (the group column headers still say Immediate/Delayed).
ID_COMPARISON_LITERAL = "ID Immediate vs Delayed"


def format_comparison(raw_comparison):
    """
    'rigid v nonrigid (-F)' -> 'Rigid vs nonrigid (-F)'
    'pPM v pGO (F)'         -> 'pPM vs pGO (F)'   (technical abbrev unchanged)
    Only the first letter is capitalized; 'v' -> 'vs' wherever it separates
    two compared groups. ID plots are a documented exception handled by the
    caller (comparison text becomes literally "ID").
    """
    if raw_comparison in COMPARISON_TITLE_OVERRIDES:
        return COMPARISON_TITLE_OVERRIDES[raw_comparison]
    s = re.sub(r"\bv\b", "vs", raw_comparison)
    return _capitalize_first_unless_abbrev(s)


def format_group_name(raw_name):
    """Column-header / group-name version of the same capitalization rule."""
    return _capitalize_first_unless_abbrev(raw_name.strip())


# ──────────────────────────────────────────────────────────────────────
# 3. Outcome-name formatting (handoff §2.3)
# ──────────────────────────────────────────────────────────────────────

# Raw `outcome` strings actually present in meta_analysis_data.csv, mapped to
# their display form. Deliberately explicit per-key (not derived by regex) —
# add an entry here for any new raw outcome string rather than guessing.
OUTCOME_TITLE_MAP = {
    "<30 Mortality": "<30 Day Mortality",
    "CW Instability": "Chest Wall Instability",
    "Dehiscience": "Dehiscence",               # note: raw data misspells this
    "Flap Loss": "Flap Loss",
    "Hematoma": "Hematoma",
    "Hernia": "Hernia",
    "Impaired Pulm Fxn": "Impaired Pulmonary Function",
    "Infx [Prosthetic]": "Prosthetic Infection",
    "Infx [Wound]": "Wound Infection",
    "LOS": "Length of Stay",
    "Material Fracture": "Material Fracture",
    "Mortality": "Mortality",
    "Necrosis": "Necrosis",
    "Op Time": "Operative Time",
    "Readmission": "Readmission",
    "Reoperation": "Reoperation",
    "Seroma": "Seroma",
    "Vasc Comp": "Vascular Complications",
    # LF-pipeline outcome keys (run_lf_id_meta.py / lf_paired_correlation_analysis.py):
    # display verbatim, confirmed against revman_forest_plots_20260815/
    # (LF_FEV1_L_primary_r097.png, LF_FEV1pct_LOOexclZhao_r074.png,
    # LF_FVC_L_primary_r098.png, LF_FVCpct_LOOexclZhao_r065.png,
    # LF_DLCO_ml-min_primary_r09.png, LF_DLCOpct_primary_r07.png).
    "FEV1 (L)": "FEV1 (L)",
    "FEV1%": "FEV1%",
    "FVC (L)": "FVC (L)",
    "FVC%": "FVC%",
    "DLCO (ml/min)": "DLCO (ml/min)",
    "DLCO%": "DLCO%",
    # NOTE: "FEV1_FVC" (the FEV1/FVC ratio pool) is deliberately NOT mapped —
    # no archived plot or handoff text confirms whether its display form is
    # "FEV1/FVC" or the raw "FEV1_FVC". Left unmapped; raises loudly if it
    # is ever needed.
    # ID-pipeline outcome keys (run_lf_id_meta.py's run_id()): "Mortality",
    # "Reoperation", "Necrosis" already covered above (identical CoRT keys,
    # reused as-is). These are ID-specific additions, confirmed against
    # ID_Dehiscence_primary.png, ID_Seroma-hematoma_primary.png,
    # ID_LOS_days_primary.png.
    "Dehiscence": "Dehiscence",              # ID raw key is spelled correctly
                                              # (distinct from CoRT's "Dehiscience")
    "Seroma/hematoma": "Seroma/Hematoma",
    # Confirmed with the author (2026-08-23) for the re-run:
    "FEV1_FVC": "FEV1/FVC",
    "Infection": "Infection",
    "LOS (days)": "Length of Stay (Days)",
    # NOTE: "Infection" (ID dichotomous outcome) is deliberately NOT mapped —
    # no archived plot confirms its display form. Raises loudly if needed.
}

# subgroup_label values produced by meta_analysis_pipeline.py's load_data()
# ("main" for MAIN N analyses, else the subgroup_category column).
SUBGROUP_SUFFIX = {
    "main": "Pooled across indications",
    "pooled": "Pooled across indications",
    "cardiac": "Cardiac subgroup",
    "mixed": "Mixed subgroup",
    "infection": "Infection subgroup",
    "oncological": "Oncological subgroup",
    "prophylactic": "Prophylactic subgroup",
}


def format_outcome(raw_outcome, subgroup_label, excluding_study=None, r_value=None):
    """
    Build the display outcome string per handoff §2.3/§2.4.

    - Normal:      '<Outcome> (<Main, no subgroup|Mixed subgroup|...>)'
    - Outlier exclusion: '<Outcome> (Sensitivity Analysis excluding <Author Year>)'
    - Paired-corr, primary (no exclusion): '<Outcome> (r = <value>)' — the
      subgroup suffix is dropped entirely; confirmed against
      LF_FEV1_L_primary_r097.png etc., which read "FEV1 (L) (r = 0.97)",
      NOT "FEV1 (L) (Main, no subgroup, r = 0.97)".
    - Paired-corr with an exclusion: as the line above, with ', r = <value>' appended
      before the closing paren — confirmed against
      LF_FEV1pct_LOOexclZhao_r074.png / LF_FVCpct_LOOexclZhao_r065.png.
    """
    if raw_outcome not in OUTCOME_TITLE_MAP:
        raise KeyError(
            f"format_outcome: raw outcome '{raw_outcome}' has no entry in "
            f"OUTCOME_TITLE_MAP. Add one explicitly — do not guess the "
            f"expansion."
        )
    base = OUTCOME_TITLE_MAP[raw_outcome]

    if excluding_study is not None:
        qualifier = f"Sensitivity Analysis excluding {excluding_study}"
        if r_value is not None:
            qualifier += f", r = {r_value}"
        return f"{base} ({qualifier})"

    if r_value is not None:
        return f"{base} (r = {r_value})"

    if subgroup_label not in SUBGROUP_SUFFIX:
        raise KeyError(
            f"format_outcome: subgroup_label '{subgroup_label}' has no entry "
            f"in SUBGROUP_SUFFIX. Add one explicitly — do not guess."
        )
    suffix = SUBGROUP_SUFFIX[subgroup_label]
    return f"{base} ({suffix})"


def format_outcome_zero_event_sensitivity(raw_outcome, excluded_studies_disp):
    """
    ID/LF dichotomous zero-event-arm sensitivity plots — run_lf_id_meta.py's
    "SENSITIVITY (excl <names> - zero-event arm)" role, which excludes
    *every* zero-event-arm study at once rather than one at a time — use a
    distinct phrasing from the single-study exclusion case. Not covered by
    handoff §2.3 (that section is explicitly single-study); instead
    verified against the delivered, approved archive
    (ID_Mortality_SensExclZeroEvent.png):

        '<Outcome> (Sensitivity Analysis excluding zero-event studies: '
        '<Author Year>, <Author Year>, ...)'
    """
    if raw_outcome not in OUTCOME_TITLE_MAP:
        raise KeyError(
            f"format_outcome_zero_event_sensitivity: raw outcome "
            f"'{raw_outcome}' has no entry in OUTCOME_TITLE_MAP. Add one "
            f"explicitly — do not guess the expansion."
        )
    base = OUTCOME_TITLE_MAP[raw_outcome]
    studies_str = ", ".join(excluded_studies_disp)
    return f"{base} (Sensitivity Analysis excluding zero-event studies: {studies_str})"


# ──────────────────────────────────────────────────────────────────────
# 2b. Role-string resolution
# ──────────────────────────────────────────────────────────────────────
# run_lf_id_meta.py and lf_paired_correlation_analysis.py both reuse
# meta_analysis_pipeline.make_forest_plot() unmodified, and
# pass a "role" string (e.g. "primary", "primary (r=0.97)",
# "excl Zhao (r=0.74)", "SENSITIVITY (excl Zhao - outlier)",
# "SENSITIVITY (excl Jacobs 2008, Piwnica-Worms 2020, ... - zero-event arm)")
# into the exact call-signature slot the CoRT pipeline uses for its
# subgroup_label ("main"/"mixed"/"infection"/...). This resolves that role
# string into the same shape title_bar_text/format_outcome already expect,
# so the shared pipeline code needed no changes. Every branch below is
# verified against the delivered archive (revman_forest_plots_20260815/) —
# see the docstring on each producing function. Anything unrecognized raises
# ValueError rather than guessing.

_ROLE_PRIMARY_RE = re.compile(r"^primary$")
_ROLE_PRIMARY_R_RE = re.compile(r"^primary \(r=([0-9.]+)\)$")
_ROLE_EXCL_R_RE = re.compile(r"^excl (.+?) \(r=([0-9.]+)\)$")
_ROLE_SENS_OUTLIER_RE = re.compile(r"^SENSITIVITY \(excl (.+?) - outlier\)$")
_ROLE_SENS_ZEROARM_RE = re.compile(r"^SENSITIVITY \(excl (.+?) - zero-event arm\)$")


def resolve_role(subgroup_label):
    """
    Parse the `subgroup_label` argument exactly as received by
    title_bar_text (i.e. whatever meta_analysis_pipeline.py's
    `_render_revman_forest` was called with in that slot). Returns a dict:

      {"subgroup_label": <SUBGROUP_SUFFIX key>}               CoRT, or LF/ID "primary"
      {"subgroup_label": <key>, "r_value": <str>}              LF paired-corr "primary (r=X)"
      {"excluding_study": <raw study name>, "r_value": <str>}   LF paired-corr "excl X (r=Y)"
      {"excluding_study": <raw study name>}                      LF/ID "SENSITIVITY (excl X - outlier)"
      {"zero_event_studies": [<raw study name>, ...]}          ID "SENSITIVITY (excl X, Y - zero-event arm)"

    Raises ValueError for anything unrecognized — never guesses.
    """
    if subgroup_label in SUBGROUP_SUFFIX:
        return {"subgroup_label": subgroup_label}

    if _ROLE_PRIMARY_RE.match(subgroup_label):
        return {"subgroup_label": "pooled"}

    m = _ROLE_PRIMARY_R_RE.match(subgroup_label)
    if m:
        return {"subgroup_label": "pooled", "r_value": m.group(1)}

    m = _ROLE_EXCL_R_RE.match(subgroup_label)
    if m:
        return {"excluding_study": m.group(1), "r_value": m.group(2)}

    m = _ROLE_SENS_OUTLIER_RE.match(subgroup_label)
    if m:
        return {"excluding_study": m.group(1)}

    m = _ROLE_SENS_ZEROARM_RE.match(subgroup_label)
    if m:
        names = [n.strip() for n in m.group(1).split(",")]
        return {"zero_event_studies": names}

    raise ValueError(
        f"resolve_role: subgroup_label/role '{subgroup_label}' is not a "
        f"known CoRT subgroup_label and doesn't match any known LF/ID role "
        f"pattern (primary / primary (r=X) / excl X (r=Y) / "
        f"SENSITIVITY (excl X - outlier) / "
        f"SENSITIVITY (excl X, Y - zero-event arm)). Add explicit handling "
        f"— do not guess the wording."
    )


def title_bar_text(raw_comparison, raw_outcome, subgroup_label,
                    excluding_study=None, r_value=None, id_plot=None):
    """'<Comparison>  |  Outcome: <Outcome>' per handoff §2.4.

    id_plot=None auto-detects the ID exception from raw_comparison (handoff
    §2.2: "ID plots are the exception: the comparison is written as just
    'ID'"); pass an explicit True/False to override.

    When excluding_study and r_value are both left as None, subgroup_label is
    resolved via resolve_role() — this is what lets run_lf_id_meta.py and
    lf_paired_correlation_analysis.py's role strings flow through unchanged.
    A caller that already knows its excluding_study/r_value (i.e. the CoRT
    call sites in meta_analysis_pipeline.py) bypasses role resolution
    entirely, exactly as before.
    """
    if id_plot is None:
        id_plot = raw_comparison == ID_COMPARISON_LITERAL
    comparison_disp = "ID" if id_plot else format_comparison(raw_comparison)

    zero_event_studies = None
    if excluding_study is None and r_value is None:
        resolved = resolve_role(subgroup_label)
        subgroup_label = resolved.get("subgroup_label", subgroup_label)
        excluding_study = resolved.get("excluding_study")
        r_value = resolved.get("r_value")
        zero_event_studies = resolved.get("zero_event_studies")

    if zero_event_studies is not None:
        excluded_disp = [clean_study_label(n) for n in zero_event_studies]
        outcome_disp = format_outcome_zero_event_sensitivity(raw_outcome, excluded_disp)
    else:
        if excluding_study is not None:
            # Idempotent: already-cleaned labels (e.g. from
            # the pipeline's plot helpers, which clean before
            # calling) pass through unchanged; raw bare surnames from a
            # role string get cleaned here.
            excluding_study = clean_study_label(excluding_study)
        outcome_disp = format_outcome(raw_outcome, subgroup_label,
                                       excluding_study=excluding_study, r_value=r_value)
    return f"{comparison_disp}  |  Outcome: {outcome_disp}"


def favors_labels(raw_outcome, higher_is_better_outcomes, groupA_disp, groupB_disp):
    """'Favours [X]' British-spelling captions per handoff §5."""
    if raw_outcome in higher_is_better_outcomes:
        return f"Favours [{groupB_disp}]", f"Favours [{groupA_disp}]"
    return f"Favours [{groupA_disp}]", f"Favours [{groupB_disp}]"


# ──────────────────────────────────────────────────────────────────────
# 4. Model selection (handoff §3)
# ──────────────────────────────────────────────────────────────────────

METHOD_NAMES = {
    ("binary", "fixed"): "M-H, Fixed, 95% CI",
    ("binary", "random"): "M-H, Random, 95% CI",
    ("continuous", "fixed"): "IV, Fixed, 95% CI",
    ("continuous", "random"): "IV, Random, 95% CI",
}

EFFECT_NAMES = {
    "binary": "Odds Ratio",
    "continuous": "Mean Difference",
}

# Two documented exceptions where the author explicitly kept Random despite
# the k=2-Fixed/k>=3-Random rule (handoff §3). Keyed by a caller-chosen tag;
# neither applies to the CoRT pipeline's own plots today (both are in the ID
# and LF pipelines respectively) but the table exists here as the single
# place new exceptions get added — never silently "fix" a model the author
# has specified.
MODEL_EXCEPTIONS = {
    "ID_Mortality": "random",     # k = 6, correctly Random
    "LF_FVC_LOO_exclZhao": "random",
}


def model_exception_key_for(raw_comparison, raw_outcome, subgroup_label, excluding_study=None):
    """
    Map (comparison, outcome, subgroup_label/role, excluding_study) to a
    MODEL_EXCEPTIONS key for the two named handoff §3 exceptions, or None.

    Both exceptions are currently vacuous against the live dataset (ID
    Mortality is k=9, LF FVC%-excl-Zhao is k=4 — both already Random under
    the default k>=3 rule), but MODEL_EXCEPTIONS was previously unreachable
    from meta_analysis_pipeline.py's select_model() call site, which would
    silently flip either plot to Fixed the moment a future data update
    brought its k down to 2. Wiring this in (see the one-line change in
    meta_analysis_pipeline.py's _render_revman_forest) is the fix.
    """
    if raw_comparison == ID_COMPARISON_LITERAL and raw_outcome == "Mortality":
        return "ID_Mortality"
    if raw_outcome == "FVC%":
        if excluding_study and "Zhao" in excluding_study:
            return "LF_FVC_LOO_exclZhao"
        if isinstance(subgroup_label, str) and re.match(r"^excl Zhao\b", subgroup_label):
            return "LF_FVC_LOO_exclZhao"
    return None


def select_model(k, data_type, exception_key=None):
    """
    Returns (model, method_name, effect_name).
    model is 'fixed' or 'random'. Default rule: k=2 -> fixed, k>=3 -> random,
    overridable only via an explicit key in MODEL_EXCEPTIONS.
    """
    if exception_key is not None and exception_key in MODEL_EXCEPTIONS:
        model = MODEL_EXCEPTIONS[exception_key]
    else:
        model = "fixed" if k == 2 else "random"
    return model, METHOD_NAMES[(data_type, model)], EFFECT_NAMES[data_type]


# ──────────────────────────────────────────────────────────────────────
# 5. Statistics-text formatting (handoff §4)
# ──────────────────────────────────────────────────────────────────────

def format_p(p):
    """
    p -> P = 0.11 / P = 0.005 / P = 0.0004 / P < 0.0001, per handoff §4.
    """
    if p is None or p != p:  # NaN check without importing numpy
        return "P = NA"
    if p < 0.0001:
        return "P < 0.0001"
    if p < 0.001:
        return f"P = {p:.4f}"
    if p < 0.01:
        return f"P = {p:.3f}"
    return f"P = {p:.2f}"


def format_signed(v, decimals=2):
    """Format a number with a proper minus sign (U+2212) if negative."""
    if v != v:
        return "NA"
    magnitude = f"{abs(v):.{decimals}f}"
    return f"{MINUS}{magnitude}" if v < 0 else magnitude


def build_heterogeneity_line(tau2, Q_het, df, p_het, I2):
    return (
        f"Heterogeneity: Tau² = {tau2:.2f}; Chi² = {Q_het:.2f}, "
        f"df = {df} ({format_p(p_het)}); I² = {round(I2):.0f}%"
    )


def build_overall_effect_line(Z, p_effect):
    """Z is reported as a positive/absolute value even if computed negative."""
    return f"Test for overall effect: Z = {abs(Z):.2f} ({format_p(p_effect)})"


def build_prediction_interval_line(pi_lower, pi_upper):
    return (
        f"95% Prediction interval: [{format_signed(pi_lower)}, "
        f"{format_signed(pi_upper)}]"
    )


FOOTNOTE_SINGLE_ZERO = (
    "† Zero events in one arm; +0.5 continuity correction applied to "
    "all cells; study contributes to pooled estimate."
)
FOOTNOTE_DOUBLE_ZERO = (
    "‡ Double-zero study; no comparative information; excluded from "
    "pooled estimate."
)


# ──────────────────────────────────────────────────────────────────────
# 6. Axis-range selection + verification (handoff §6)
# ──────────────────────────────────────────────────────────────────────

import numpy as np

_LOG_CANDIDATE_TICKS = [
    0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
    1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
]


def _axis_x(v, xlim, log_scale):
    if log_scale:
        if v <= 0:
            v = xlim[0] * 5
        lo, hi = np.log10(xlim[0]), np.log10(xlim[1])
        return (np.log10(v) - lo) / (hi - lo)
    return (v - xlim[0]) / (xlim[1] - xlim[0])


def _pick_ticks(xlim, log_scale):
    if log_scale:
        ticks = [t for t in _LOG_CANDIDATE_TICKS if xlim[0] <= t <= xlim[1]]
        if 1 not in ticks:
            ticks.append(1)
        return _thin_log_ticks(sorted(ticks), xlim)
    # Linear: pick a "nice" step via matplotlib-style rounding.
    span = xlim[1] - xlim[0]
    raw_step = span / 6
    magnitude = 10 ** np.floor(np.log10(raw_step)) if raw_step > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        step = m * magnitude
        if step >= raw_step:
            break
    start = np.ceil(xlim[0] / step) * step
    ticks = []
    t = start
    while t <= xlim[1] + 1e-9:
        ticks.append(round(t, 10))
        t += step
    if 0.0 not in ticks and xlim[0] < 0 < xlim[1]:
        ticks.append(0.0)
    return sorted(set(ticks))


_MIN_TICK_GAP = 0.042        # floor, as a fraction of panel width
_PER_CHAR_GAP = 0.0205       # extra width demanded per character of tick label


def _tick_label(t):
    return ("%g" % t)


def _required_gap(ticks):
    """Tick spacing must clear the widest label, not a fixed constant."""
    widest = max((len(_tick_label(t)) for t in ticks), default=1)
    return max(_MIN_TICK_GAP, _PER_CHAR_GAP * widest)


def _thin_log_ticks(ticks, xlim, min_gap=None):
    """Drop ticks that would sit too close to their neighbour to be legible.

    On a wide log axis (an odds ratio whose CI spans several orders of
    magnitude) every candidate tick inside the range is kept by the rule
    above, and the resulting labels overprint one another — the exact defect
    handoff SS6 forbids. Keep 1 (the null-effect reference) and both ends
    unconditionally, then walk outward from 1 keeping only ticks at least
    `min_gap` of the panel width from the last one kept.
    """
    if len(ticks) < 3:
        return ticks
    if min_gap is None:
        min_gap = _required_gap(ticks)
    keep = {ticks[0], ticks[-1]}
    if 1 in ticks:
        keep.add(1)
    anchor = 1 if 1 in ticks else ticks[len(ticks) // 2]
    ai = ticks.index(anchor)
    for direction in (1, -1):
        last = anchor
        i = ai + direction
        while 0 <= i < len(ticks):
            if abs(_axis_x(ticks[i], xlim, log_scale=True)
                   - _axis_x(last, xlim, log_scale=True)) >= min_gap:
                keep.add(ticks[i])
                last = ticks[i]
            i += direction
    # an endpoint kept unconditionally may still crowd its neighbour
    out = sorted(keep)
    for end, nbr in ((0, 1), (-1, -2)):
        if len(out) > 2 and abs(_axis_x(out[end], xlim, log_scale=True)
                                - _axis_x(out[nbr], xlim, log_scale=True)) < min_gap:
            drop = out[nbr]
            if drop != 1:
                out.remove(drop)
    return out


def verify_axis_margins(xticks, ci_pairs, xlim, log_scale, min_margin=0.03):
    """Runnable per handoff §6: both tick and CI margins must be >= 3%."""
    xs = [_axis_x(t, xlim, log_scale) for t in xticks]
    ci = [_axis_x(v, xlim, log_scale) for lo, hi in ci_pairs for v in (lo, hi)]
    if not xs or not ci:
        return False
    tick_margin = min(xs[0], 1 - xs[-1])
    ci_margin = min(min(ci), 1 - max(ci))
    return tick_margin >= min_margin and ci_margin >= min_margin


def pick_axis_range(all_lo, all_hi, log_scale, max_iterations=40):
    """
    Choose xlim/xticks bracketing the data with round tick values, then grow
    the range until the >=3% margin rule (handoff §6) actually holds —
    verified numerically, not eyeballed. Raises if it cannot converge, so a
    bad axis range fails loudly instead of shipping.
    """
    lo = min(all_lo)
    hi = max(all_hi)
    ci_pairs = list(zip(all_lo, all_hi))

    if log_scale:
        safe_lo = min([v for v in all_lo if v > 0], default=lo)
        x_min = max(safe_lo * 0.6, 1e-6)
        x_max = hi * 1.6
    else:
        span = hi - lo if hi > lo else max(abs(hi), 1.0)
        pad = span * 0.2
        x_min = lo - pad
        x_max = hi + pad

    for _ in range(max_iterations):
        xlim = (x_min, x_max)
        xticks = _pick_ticks(xlim, log_scale)
        if verify_axis_margins(xticks, ci_pairs, xlim, log_scale):
            return xlim, xticks
        if log_scale:
            x_min /= 1.15
            x_max *= 1.15
        else:
            grow = (x_max - x_min) * 0.08
            x_min -= grow
            x_max += grow

    raise AssertionError(
        f"pick_axis_range: could not find an xlim/xticks combination "
        f"satisfying the >=3% margin rule after {max_iterations} attempts "
        f"(data range [{lo}, {hi}], log_scale={log_scale})."
    )
