#!/usr/bin/env python3
"""Rebuild duplicate_cells.json for the eFigure 1 stars.

Two cells are the SAME analysis only if they share the outcome, the exact set of
contributing studies AND the resulting estimate. The study set alone is not
enough: two comparisons can draw on the same studies while contrasting different
arms (single vs dual flap and pPM vs pLD both use Falkner 2021, Greig 2007 and
Lee 2010 for necrosis, but compare different groups within them).
"""
import json
import pandas as pd
from collections import defaultdict

CELLS = json.load(open("/tmp/run/efig1_data.json"))["cells"]
S = pd.read_csv("/tmp/run/output/meta_analysis_summary.csv")
S = S[~S.subgroup.astype(str).str.contains("SENSITIVITY")]

info = {}
for _, r in S.iterrows():
    cs = r.contributing_studies
    info[(r.comparison_name, r.subgroup, r.outcome_name)] = (
        frozenset(x.strip() for x in str(cs).split(";")) if isinstance(cs, str) else frozenset(),
        None if pd.isna(r.total_patients) else int(r.total_patients),
        None if pd.isna(r.pooled_estimate) else round(float(r.pooled_estimate), 6),
        None if pd.isna(r.ci_lower) else round(float(r.ci_lower), 6),
    )

groups = defaultdict(list)
for c in CELLS:
    key = (c["comparison"], c["stratum"], c["outcome"])
    d = info.get(key)
    if not c["k"] or not d or not d[0]:
        continue
    groups[(c["outcome"],) + d].append(key)

out = []
for ident, members in groups.items():
    if len(members) < 2:
        continue
    label = sorted(f"{comp} [{strat}]" for comp, strat, _ in members)
    for comp, strat, outc in members:
        out.append({"comparison": comp, "stratum": strat, "outcome": outc, "group": label})

json.dump(out, open("/tmp/run/duplicate_cells.json", "w"), indent=1)
pair_groups = {tuple(sorted({tuple(x["group"]) for x in out if x["outcome"] == o}))
               for o in {x["outcome"] for x in out}}
print(f"duplicate cells: {len(out)}")
print(f"duplicate groups (outcome-specific): {sum(1 for m in groups.values() if len(m) > 1)}")
print(f"redundant copies: {sum(len(m) - 1 for m in groups.values() if len(m) > 1)}")
print(f"distinct comparison-stratum groupings: {len({tuple(x['group']) for x in out})}")
