#!/usr/bin/env python3
"""Build meta_analysis_data.csv for the 12 final CoRT comparisons.

Emits one row per (comparison, stratum, outcome, study, arm) in the long
schema meta_analysis_pipeline.load_data() expects.
"""
import csv, openpyxl
from collections import defaultdict

WB   = "master.xlsx"
OUT  = "meta_analysis_data.csv"

MESH = {"synmesh", "biomesh", "semisyn"}
NONFLAP = MESH | {"pros", "rewiring"}

# outcome -> column(s) in CoRT Raw Data
BIN = {"Infx [Wound]":8, "Infx [Prosthetic]":9, "Seroma":10, "Hematoma":11,
       "Necrosis":12, "Dehiscience":13, "Hernia":14, "Flap Loss":15,
       "Vasc Comp":16, "Impaired Pulm Fxn":17, "CW Instability":18,
       "<30 Mortality":19, "Mortality":20, "Readmission":25, "Reoperation":26}
CONT = {"Op Time":(21,22), "LOS":(23,24)}
ORDER = ["Infx [Wound]","Infx [Prosthetic]","Dehiscience","CW Instability","Necrosis",
         "Flap Loss","Seroma","Hematoma","Hernia","Vasc Comp","Impaired Pulm Fxn",
         "<30 Mortality","Mortality","Reoperation","Readmission","LOS","Op Time"]

def load_rows():
    ws = openpyxl.load_workbook(WB, data_only=True)["CoRT Raw Data"]
    rows = []
    for r in range(2, ws.max_row + 1):
        recon = ws.cell(r, 6).value
        if recon in (None, ""):
            continue
        tk = frozenset(t.strip() for t in str(recon).split(",") if t.strip())
        rows.append(dict(
            sid   = ws.cell(r, 1).value,
            name  = str(ws.cell(r, 2).value).strip(),
            year  = ws.cell(r, 3).value,
            ind   = str(ws.cell(r, 4).value).strip().lower(),
            n     = ws.cell(r, 5).value or 0,
            tk    = tk,
            bin   = {k: ws.cell(r, c).value for k, c in BIN.items()},
            cont  = {k: (ws.cell(r, m).value, ws.cell(r, s).value) for k, (m, s) in CONT.items()},
        ))
    for x in rows:
        x["flaps"] = x["tk"] - NONFLAP
        x["mesh"]  = bool(x["tk"] & MESH)
        x["pros"]  = "pros" in x["tk"]
        x["rew"]   = "rewiring" in x["tk"]
        x["strat"] = "rigid" if x["pros"] else ("nonrigid" if (x["mesh"] or x["rew"]) else "none")
        x["study"] = f"{x['name']} {x['year']}"
    return rows

def P(a, b):
    return (lambda x: a in x["flaps"] and b not in x["flaps"]), \
           (lambda x: b in x["flaps"] and a not in x["flaps"])

# (family, label, arm1 name, arm2 name, arm1 predicate, arm2 predicate)
COMPARISONS = [
 ("Skeletal","rigid v non-rigid","rigid","non-rigid",
   lambda x: x["strat"]=="rigid", lambda x: x["strat"]=="nonrigid"),
 ("Skeletal","rigid v soft mesh","rigid","soft mesh",
   lambda x: x["strat"]=="rigid", lambda x: x["mesh"] and not x["pros"] and not x["rew"]),
 ("Skeletal","rigid v rewiring","rigid","rewiring",
   lambda x: x["strat"]=="rigid", lambda x: x["rew"] and not x["pros"]),
 ("Skeletal","soft mesh v flap alone","soft mesh","flap alone",
   lambda x: x["mesh"] and not x["pros"] and not x["rew"], lambda x: x["strat"]=="none"),
 ("Skeletal","rewiring v flap alone","rewiring","flap alone",
   lambda x: x["rew"] and not x["pros"] and not x["mesh"], lambda x: x["strat"]=="none"),
 ("Flap","single v dual flap","single flap","dual flap",
   lambda x: len(x["flaps"])==1, lambda x: len(x["flaps"])>=2),
 ("Flap","muscle flap v omentum","muscle flap","omentum",
   lambda x: bool(x["flaps"]) and "pGO" not in x["flaps"], lambda x: "pGO" in x["flaps"]),
 ("Flap","pPM v pGO","pPM","pGO", *P("pPM","pGO")),
 ("Flap","pPM v pLD","pPM","pLD", *P("pPM","pLD")),
 ("Flap","pPM v pRA","pPM","pRA", *P("pPM","pRA")),
 ("Flap","pedicled v free","pedicled","free",
   lambda x: bool(x["flaps"]) and all(t[0]=="p" for t in x["flaps"]),
   lambda x: bool(x["flaps"]) and all(t[0]=="f" for t in x["flaps"])),
 ("Additive","pPM v pPM + pGO","pPM","pPM + pGO",
   lambda x: "pPM" in x["flaps"] and "pGO" not in x["flaps"],
   lambda x: "pPM" in x["flaps"] and "pGO" in x["flaps"]),
]

STRATA = [(None,"pooled","MAIN"), ("oncological","oncological","SUBGROUP"),
          ("prophylactic","cardiac","SUBGROUP"), ("infection","infection","SUBGROUP")]

BAD = (None, "", "-")

def main():
    rows = load_rows()
    sid_of = {}
    for x in rows:
        sid_of.setdefault(x["study"], x["sid"])

    out = []
    for ci, (family, label, a_name, b_name, A, B) in enumerate(COMPARISONS, 1):
        for ind, sub_cat, atype in STRATA:
            buckets = defaultdict(lambda: {"comp1": [], "comp2": []})
            for x in rows:
                if ind and x["ind"] != ind:
                    continue
                if A(x):
                    buckets[x["study"]]["comp1"].append(x)
                elif B(x):
                    buckets[x["study"]]["comp2"].append(x)
            both = {s: d for s, d in buckets.items() if d["comp1"] and d["comp2"]}
            if not both:
                continue
            atype_full = f"MAIN {ci}" if atype == "MAIN" else f"SUBGROUP {ci}"
            for outcome in ORDER:
                is_cont = outcome in CONT
                for study, d in sorted(both.items()):
                    cohorts = d["comp1"] + d["comp2"]
                    if is_cont:
                        vals = [y["cont"][outcome] for y in cohorts]
                        if any(m in BAD or s in BAD or s == 0 for m, s in vals):
                            continue
                    else:
                        if any(y["bin"][outcome] in BAD for y in cohorts):
                            continue
                    for arm in ("comp1", "comp2"):
                        for y in d[arm]:
                            if is_cont:
                                mean, sd = y["cont"][outcome]
                                val, sdv = mean, sd
                            else:
                                val, sdv = y["bin"][outcome], ""
                            out.append(dict(
                                comparison=label, subgroup_category=sub_cat,
                                analysis_type=atype_full, outcome=outcome,
                                study_id=sid_of[study], study_name=study,
                                comp_arm=arm, n=y["n"], val=val, sd=sdv,
                                comp1=a_name, comp2=b_name, family=family,
                            ))

    cols = ["comparison","subgroup_category","analysis_type","outcome","study_id",
            "study_name","comp_arm","n","val","sd","comp1","comp2","family"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"{OUT}: {len(out)} rows")
    keys = {(r["comparison"], r["subgroup_category"], r["outcome"]) for r in out}
    print(f"analysis groups written: {len(keys)}")

if __name__ == "__main__":
    main()
