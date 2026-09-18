#!/usr/bin/env python3
"""8.29 edits to the supplement: restore the sensitivity-analysis protocol that
was reverted to the withdrawn leave-one-out text, remap the eTable references,
and rewrite the four eFigure captions to match the figures as they now stand.
"""
import sys, docx
sys.path.insert(0, "/tmp/doc")
from docxlib import annotate, set_text, set_caption

SRC, DST = "supp18.docx", "supp19.docx"
d = docx.Document(SRC)
before = d.element.body.xml.count("<w:sdt>")

def all_paras():
    yield from d.paragraphs
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                yield from c.paragraphs

def pw(needle, occ=0):
    hits = [p for p in all_paras() if needle in annotate(p)]
    if not hits:
        raise LookupError(needle)
    return hits[occ]

def sub(p, pairs):
    t = annotate(p)
    for a, b in pairs:
        assert a in t, f"not found: {a!r}"
        t = t.replace(a, b)
    set_text(p, t)

# ── eMethods ────────────────────────────────────────────────────────────
# The leave-one-out protocol was withdrawn from the review; the pre-specified
# clinical outlier is the only exclusion anywhere in the analysis.
set_text(pw("Sensitivity analyses. Leave-one-out analyses were performed"),
 "Sensitivity analyses. One study was excluded as a pre-specified clinical "
 "outlier: Zhao et al., whose cohort entered with FEV1 of 41.83% and FVC of "
 "39.18% predicted against a range of 78.1–98.6% in the other lung-function "
 "studies. That exclusion was specified on clinical grounds and is reported "
 "alongside the corresponding primary estimate for FEV1 and FVC percent "
 "predicted. No other sensitivity analysis was performed: no leave-one-out "
 "analysis, no exclusion of the largest contributor to heterogeneity, and no "
 "exclusion of studies with a zero-event arm. Every other estimate reported "
 "in this review is the primary estimate on all eligible studies.")

sub(pw("based on the outcome’s confidence intervals are presented in eTable 8."),
    [("presented in eTable 8.", "presented in eTable 7.")])

# ── eTable 7 caption ────────────────────────────────────────────────────
sub(pw("the primary value for each outcome is the one derived in Table 2"),
    [("the one derived in Table 2", "the one derived in eTable 4")])

# ── eFigure captions ────────────────────────────────────────────────────
set_caption(pw("eFigure 1. Coverage heatmap"),
 "eFigure 1. Coverage heatmap of the comparison of reconstructive techniques "
 "analysis. Contributing studies (k) and total patients for every combination "
 "of the twelve comparisons, four indication strata and seventeen "
 "postoperative outcomes. Green cells had two or more contributing studies and "
 "were carried forward to analysis, yellow cells reached statistical "
 "significance, orange cells had a single contributing study and red cells had "
 "none. A starred cell reports the same outcome on the same contributing "
 "studies with the same compared arms as another cell in the grid, and is "
 "therefore not an independent analysis; 70 cells in 14 such groups are "
 "marked, leaving 41 redundant copies among the 816 cells.")

set_caption(pw("eFigure 2. Forest plots for the statistically significant comparison"),
 "eFigure 2. Forest plots for the statistically significant comparison of "
 "reconstructive techniques analyses pooled across indications. The plots run "
 "in order: rigid versus non-rigid fixation for reoperation and for length of "
 "stay; rewiring versus flap alone for mortality and for reoperation; single "
 "versus dual flap for hematoma; pectoralis major versus rectus abdominis for "
 "flap loss and for reoperation; and pectoralis major alone versus pectoralis "
 "major with omentum for 30-day mortality. Each plot names its comparison and "
 "outcome in the header bar. Three further pooled analyses reached "
 "significance but rest on exactly the studies, and the same compared arms, of "
 "an indication-specific analysis, and are shown there instead: rigid versus "
 "rewiring for reoperation and for length of stay, which are the cardiac "
 "analyses in Figure 7, and rewiring versus flap alone for readmission, which "
 "is the infection analysis in Figure 5. Prediction intervals are shown where "
 "four or more studies contribute.")

set_caption(pw("eFigure 3. Forest plots for the immediate versus delayed"),
 "eFigure 3. Forest plots for the statistically significant immediate versus "
 "delayed timing analyses pooled across indications: mortality, then seroma or "
 "hematoma. The pooled mortality estimate does not persist when restricted to "
 "sternal wound infection (Figure 5). Pooled dehiscence and pooled length of "
 "stay also reached significance but rest on exactly the studies of their "
 "infection-stratum counterparts, and are shown once, in Figure 5. Prediction "
 "intervals are shown where four or more studies contribute.")

set_caption(pw("eFigure 4. Forest plots for the lung-function analysis"),
 "eFigure 4. Forest plots for the lung-function analysis, pooled across "
 "indications. The plots run in order: FEV1 in litres, FVC in litres, DLCO in "
 "mL/min/mmHg and DLCO as percent predicted, followed by the two pre-specified "
 "outlier analyses excluding Zhao et al., for FEV1 percent predicted and for "
 "FVC percent predicted. The surgical indication of each study is printed "
 "beside its label, since this stream could not be stratified: absolute and "
 "percent-predicted forms of a measure cannot be pooled together and no "
 "indication reached two contributing studies for any single measure. Each "
 "analysis uses the outcome-specific pre-/postoperative correlation "
 "coefficient in eTable 4, shown in the plot title as r. For comparisons with "
 "four or more contributing studies (k ≥ 4) a prediction interval is shown, "
 "indicating the range within which the true effect of a future study in a "
 "comparable clinical context is expected to fall.")

d.save(DST)
print("sdt before/after:", before,
      docx.Document(DST).element.body.xml.count("<w:sdt>"))
print("saved", DST)
