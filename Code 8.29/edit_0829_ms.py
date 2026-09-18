#!/usr/bin/env python3
"""8.29 edits to the manuscript: figure renumbering, table renumbering, and
removal of every pooled result that rests on the same studies as an
indication-specific result.
"""
import sys, docx
sys.path.insert(0, "/tmp/doc")
from docxlib import annotate, set_text, set_caption, delete_para

SRC, DST = "ms23.docx", "ms24.docx"
d = docx.Document(SRC)
ps = d.paragraphs
before = d.element.body.xml.count("<w:sdt>")

def find(prefix, occ=0):
    hits = [p for p in ps if p.text.strip().startswith(prefix)]
    if not hits:
        raise LookupError(prefix)
    return hits[occ]

def sub(p, pairs):
    """Literal replacements on the citation-annotated text of one paragraph."""
    t = annotate(p)
    for old, new in pairs:
        if old not in t:
            raise ValueError(f"not found: {old!r}\n  in: {t[:160]}")
        t = t.replace(old, new)
    set_text(p, t)

def para_with(needle, occ=0):
    hits = [p for p in ps if needle in annotate(p)]
    if not hits:
        raise LookupError(needle)
    return hits[occ]

# ── Methods ─────────────────────────────────────────────────────────────
# eTable 3 (classification codes) and eTable 4 (the twelve comparisons) were
# withdrawn from the supplement; Figure 1 carries both.
sub(para_with("(Figure 1A, eTable 3)"), [
    ("(Figure 1A, eTable 3)", "(Figure 1A)"),
    ("(Figure 1C; eTable 4)", "(Figure 1C)"),
])
sub(para_with("Definitions are given in eTable 5."),
    [("Definitions are given in eTable 5.", "Definitions are given in eTable 3.")])
sub(para_with("derivation methods and rationale are provided in eTable 8."),
    [("provided in eTable 8.", "provided in eTable 4.")])

# ── Results: where the results live ─────────────────────────────────────
sub(para_with("All indication-stratified and pooled significant results"), [
 ("All indication-stratified and pooled significant results, with duplicate "
  "analyses resting on identical sets of studies ommitted, are summarized in "
  "eTable 6, and visualized in Figure 4 (indication) and eFigure 2 (pooled). "
  "Forest plots for significant pooled CoRT and ID results are depicted in "
  "eFigures 3 and 4, respectively. All nonsignificant results are reported in "
  "eTable 7.",
  "Every indication-specific analysis is listed in eTable 5 and every pooled "
  "analysis in eTable 6. A result is reported once: where a pooled analysis "
  "and an indication-specific analysis rest on the same studies and compare "
  "the same arms they are a single analysis, and it is reported under the "
  "indication. Twenty-four analyses reached significance on this basis — 8 "
  "within a single indication (Figure 4), 14 pooled across indications "
  "(eFigures 2, 3 and 4) and 2 pre-specified outlier analyses in the "
  "lung-function stream (eFigure 4)."),
])

# Figure 10 -> Figure 9, and its panels were consolidated to three.
sub(para_with("without specifying count (Figure 10C)"), [
    ("(Figure 10C)", "(Figure 9A)"),
    ("pre-operative antibiotics by one (Figure 10D).",
     "pre-operative antibiotics by one (Figure 9A)."),
])
sub(para_with("the highest of any indication (Figure 10D)"),
    [("(Figure 10D)", "(Figure 9A)")])

# ── Results: pooled analyses ────────────────────────────────────────────
# Readmission (rewiring vs flap alone) rests on the two infection studies
# already reported above; pooled dehiscence and pooled length of stay rest on
# the infection-stratum studies already reported above. None is repeated here.
sub(para_with("The 138 analyses pooling every eligible study"), [
 ("Rewiring alone carried higher odds of mortality (OR 2.85 [1.01–8.10], k=6), "
  "reoperation (OR 7.99 [1.72–37.24], k=4) and readmission (OR 12.71 "
  "[3.94–41.05], k=2) than flap coverage.",
  "Rewiring alone carried higher odds of mortality (OR 2.85 [1.01–8.10], k=6) "
  "and reoperation (OR 7.99 [1.72–37.24], k=4) than flap coverage; the pooled "
  "readmission estimate rests on the two infection studies reported above and "
  "is the same analysis."),
 ("Pooled across all nine ID studies, immediate reconstruction was associated "
  "with lower mortality (OR 0.48 [0.26–0.90]), lower dehiscence (OR 0.41 "
  "[0.22–0.77]), shorter stay (MD −8.82 days) and higher odds of seroma or "
  "hematoma (OR 3.52 [1.12–11.09]). All 214 nonsignificant analyses are "
  "listed in eTable 7.",
  "Pooled across all nine ID studies, immediate reconstruction was associated "
  "with lower mortality (OR 0.48 [0.26–0.90]) and higher odds of seroma or "
  "hematoma (OR 3.52 [1.12–11.09]); pooled dehiscence and length of stay draw "
  "on the infection studies reported above and are the same analyses. All 214 "
  "nonsignificant analyses are listed in eTables 5 and 6."),
])

# ── Results: lung function ──────────────────────────────────────────────
sub(para_with("The LF stream is pooled by necessity."), [
    ("(Figure 8; eFigure 2)", "(eFigure 4)"),
    ("125% in FVC% (Figure 9)", "125% in FVC% (Figure 8)"),
    ("correlation coefficients (eTable 8)", "correlation coefficients (eTable 4)"),
    ("sensitivity grids are reported in eTable 9.",
     "sensitivity grids are reported in eTable 7."),
])

# ── Results: quality ────────────────────────────────────────────────────
sub(para_with("driven by serious or critical confounding (Figure 11)"),
    [("(Figure 11)", "(Figure 10)")])
sub(para_with("none of 14 using soft mesh alone (Figure 10A, 10B)"),
    [("(Figure 10A, 10B)", "(Figure 9B)")])

# ── Discussion ──────────────────────────────────────────────────────────
sub(para_with("the study-level pattern in Figure 9,"),
    [("the study-level pattern in Figure 9,", "the study-level pattern in Figure 8,")])
sub(para_with("too inconsistently to enter any model (Figure 10)"),
    [("(Figure 10)", "(Figure 9)")])

# ── Captions ────────────────────────────────────────────────────────────
set_caption(find("Figure 1."), annotate(find("Figure 1.")).replace(
    "Each was assessed pooled across indications and within the infection, "
    "oncological and cardiac strata for each of seventeen outcomes, pooling "
    "requiring at least two contributing studies. Starred cells yielded at "
    "least one statistically significant pooled effect.",
    "Each was assessed within the infection, oncological and cardiac strata "
    "and again pooled across indications, for each of seventeen outcomes, "
    "pooling requiring at least two contributing studies. A star marks a "
    "comparison that yielded at least one statistically significant result in "
    "that stratum. Cardiac rigid-versus-rewiring reproduces cardiac "
    "rigid-versus-non-rigid exactly, and is starred once, under the latter."))

set_caption(find("Figure 3."), annotate(find("Figure 3.")).replace(
    "(G) Country of the first author's primary affiliation.",
    "(G) Country of the corresponding author's institution.").replace(
    "(G) Country of the first author’s primary affiliation.",
    "(G) Country of the corresponding author’s institution."))

set_caption(find("Figure 4."),
 "Figure 4. Statistically significant results within a single indication. "
 "Each section carries the results for one indication: infection (A), "
 "oncological (B) and cardiac (C). Within a section, odds ratios are plotted "
 "on a logarithmic scale and mean differences on a linear scale below them, "
 "with negative differences indicating a lower value in the index arm; "
 "horizontal bars are 95% confidence intervals and the index arm is the group "
 "named first. Colour denotes analysis stream and the chip beside each "
 "estimate denotes heterogeneity. Fixed-effect models were used at k=2 and "
 "random-effects models at k≥3; I² at k=2 describes observed dispersion and "
 "does not enter estimation. Where an analysis rests on the same studies and "
 "the same compared arms as a pooled analysis it is shown here and not again "
 "among the pooled estimates. No adjustment was made for multiplicity. "
 "Estimates pooled across all indications are shown in eFigures 2, 3 and 4. "
 "k, contributing studies; MD, mean difference; OR, odds ratio.")

set_caption(find("Figure 5."),
 "Figure 5. Forest plots for the statistically significant analyses in the "
 "infection stratum. The plots run in order: immediate versus delayed "
 "reconstruction for dehiscence and for length of stay; rewiring versus flap "
 "alone for readmission; single versus dual flap for necrosis; and pedicled "
 "versus free flaps for necrosis. Each plot names its comparison and outcome "
 "in the header bar. Dehiscence, length of stay and readmission each rest on "
 "studies that are all infection-related, so the pooled analysis of each is "
 "the same analysis and is reported here rather than among the pooled "
 "estimates. The infection-restricted mortality estimate is not statistically "
 "significant and is reported in eTable 5. Prediction intervals are shown "
 "where four or more studies contribute.")

set_caption(find("Figure 7."),
 "Figure 7. Forest plots for the cardiac stratum. Rigid fixation versus "
 "rewiring, for reoperation and then for length of stay. These are the only "
 "estimable comparisons in this indication; because every cardiac study "
 "comparing rigid fixation with a less rigid construct compared it with "
 "rewiring, the cardiac rigid-versus-non-rigid analyses share the same "
 "contributing studies and estimates and are not shown separately, and the "
 "corresponding pooled rigid-versus-rewiring analyses are the same analyses "
 "again. Prediction intervals are shown where four or more studies contribute.")

set_caption(find("Figure 9."),
 "Figure 9. Reporting of potential confounders and of industry involvement. "
 "(A) Proportion of studies in each indication reporting radiotherapy, "
 "antibiotic exposure and obesity at all; bars count studies that mention the "
 "item, not patients who received it. (B) Financial relationships by the "
 "construct the study used, divided into four mutually exclusive states so "
 "that a declared device-industry tie is separated from a study that merely "
 "carries a disclosure heading. (C) Share of the pooled weight contributed by "
 "studies declaring a device-industry tie, in each significant "
 "rigid-fixation result. Declared device-industry ties, all in studies using "
 "rigid plating unless noted: Allen 2017 (cardiac), Zimmer Biomet; "
 "Bennett-Guerrero 2011 (cardiac), KLS Martin; George 2014 (mixed), DePuy "
 "Synthes; Peigh 2017 (cardiac), Biomet; Royse 2020 (cardiac), Zimmer Biomet; "
 "Tasnim 2024 (oncological), KLS Martin and Zimmer; Tugulan 2020 (cardiac), "
 "Abbott, TandemLife and Abiomed; and Kamel 2019 (infection), SigmaSurgical "
 "and Stryker, which used no exogenous material. Weight in the third panel is "
 "each study's contribution to the pooled estimate under the model used for "
 "that analysis.")

set_caption(find("Figure 11."),
 "Figure 10. Risk-of-bias assessment. Cohort studies rated with ROBINS-I "
 "(A, n = 54), case series with the JBI case-series checklist (B, n = 45) and "
 "randomized trials with the JBI randomized-trial checklist (C, n = 4), shown "
 "as traffic-light figures with included studies listed at left. JBI items are "
 "numbered Q1 onward and identified beside each legend by the topic the item "
 "addresses; the full instrument wording is standard and is not reproduced.")

# The prediction-interval note sat under the old Figure 8 (the lung-function
# forest plots). That figure is now eFigure 4 and the note travels with it.
delete_para(para_with("For comparisons with four or more contributing studies (k ≥ 4), "
                      "a prediction interval is shown"))

d.save(DST)
chk = docx.Document(DST)
print("sdt before/after:", before, chk.element.body.xml.count("<w:sdt>"))
print("saved", DST)
