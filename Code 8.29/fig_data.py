#!/usr/bin/env python3
"""Datasets for Figure 3 (descriptive map) and eFigure 1 (CoRT coverage heatmap)."""
import json, openpyxl, pandas as pd
from collections import Counter, defaultdict

wb = openpyxl.load_workbook("master.xlsx", data_only=True)

# ---------- stream membership + indications (Organization sheet) ----------
org = wb["Organization"]
cort = [(org.cell(r,1).value.strip(), org.cell(r,2).value, org.cell(r,4).value)
        for r in range(2, 89) if org.cell(r,1).value]
lf   = [(org.cell(r,1).value.strip(), org.cell(r,2).value, org.cell(r,4).value)
        for r in range(92,100)]
idd  = [(org.cell(r,1).value.strip(), org.cell(r,2).value, org.cell(r,4).value)
        for r in range(104,113)]

# ---------- panel A: publication year, 5-year bins, by stream ----------
def bin5(y): 
    lo = (int(y)//5)*5
    return f"{lo}–{lo+4}"
bins = defaultdict(lambda: {"CoRT":0,"LF":0,"ID":0})
for lst, tag in ((cort,"CoRT"),(lf,"LF"),(idd,"ID")):
    for nm, yr, ind in lst:
        if tag == "LF" and nm == "Meadows":     # dual-stream study assigned to CoRT
            continue
        bins[bin5(yr)][tag] += 1
panelA = [{"bin":b, **bins[b]} for b in sorted(bins)]

# ---------- panel B: indication, by stream ----------
panelB = {}
for lst, tag in ((cort,"CoRT"),(lf,"LF"),(idd,"ID")):
    c = Counter(ind for nm,yr,ind in lst if not (tag=="LF" and nm=="Meadows"))
    panelB[tag] = dict(c)

# ---------- panels C/D: flap + structural use across the 87 CoRT studies ----
rd = wb["CoRT Raw Data"]
MESH = {"synmesh","biomesh","semisyn"}
study_tokens = defaultdict(set)
study_n = {}
for r in range(2, rd.max_row+1):
    rec = rd.cell(r,6).value
    if rec in (None,""): continue
    key = f"{str(rd.cell(r,2).value).strip()} {rd.cell(r,3).value}"
    for t in str(rec).split(","):
        t = t.strip()
        if t: study_tokens[key].add(t)

flap_use = defaultdict(lambda: {"pedicled":0,"free":0,"both":0})
rewiring_studies = 0
for st, tk in study_tokens.items():
    if "rewiring" in tk: rewiring_studies += 1
    muscles = defaultdict(set)
    for t in tk:
        if t in MESH or t in ("pros","rewiring"): continue
        if t and t[0] in "pf":
            muscles[t[1:]].add(t[0])
    for m, pref in muscles.items():
        if pref == {"p"}:   flap_use[m]["pedicled"] += 1
        elif pref == {"f"}: flap_use[m]["free"] += 1
        else:               flap_use[m]["both"] += 1
no_flap_studies = sum(1 for tk in study_tokens.values()
                      if not any(t and t[0] in "pf" and t not in MESH
                                 and t not in ("pros", "rewiring") for t in tk))
panelC = {"flaps": {m: dict(v) for m, v in sorted(
              flap_use.items(), key=lambda kv: -sum(kv[1].values()))},
          "rewiring_studies": rewiring_studies,
          "no_flap_studies": no_flap_studies,
          "total_cort_studies": len(study_tokens)}

struct = Counter(); subtypes = Counter()
for st, tk in study_tokens.items():
    rigid = "pros" in tk
    mesh  = bool(tk & MESH)
    if rigid: struct["rigid"] += 1
    if mesh:  struct["soft mesh"] += 1
    if not rigid and not mesh: struct["no exogenous material"] += 1
    for m in (tk & MESH): subtypes[m] += 1
    if rigid: subtypes["pros"] += 1
panelD = {"structural": dict(struct), "subtypes": dict(subtypes)}

# ---------- panel E: CoRT studies reporting each outcome ----------
BIN = {"Wound infection":8,"Prosthetic infection":9,"Seroma":10,"Hematoma":11,
       "Necrosis":12,"Dehiscence":13,"Hernia":14,"Flap loss":15,
       "Vascular complications":16,"Impaired pulmonary function":17,
       "Chest wall instability":18,"30-day mortality":19,"Overall mortality":20,
       "Readmission":25,"Reoperation":26}
CONT = {"Operative time":21,"Length of stay":23}
rep = defaultdict(set)
for r in range(2, rd.max_row+1):
    if rd.cell(r,6).value in (None,""): continue
    key = f"{str(rd.cell(r,2).value).strip()} {rd.cell(r,3).value}"
    for o,c in list(BIN.items())+list(CONT.items()):
        v = rd.cell(r,c).value
        if v not in (None,"","-"): rep[o].add(key)
panelE = {o: len(s) for o,s in sorted(rep.items(), key=lambda kv:-len(kv[1]))}

# ---------- panel F: patients per study ----------
tot = defaultdict(int)
for r in range(2, rd.max_row+1):
    if rd.cell(r,6).value in (None,""): continue
    key = f"{str(rd.cell(r,2).value).strip()} {rd.cell(r,3).value}"
    tot[key] += rd.cell(r,5).value or 0
lfws = wb["LF Raw Data"]; idws = wb["ID Raw Data"]
lf_n = {f"{lfws.cell(r,2).value} {lfws.cell(r,3).value}": lfws.cell(r,4).value
        for r in range(2,10)}
id_n = {f"{idws.cell(r,2).value} {idws.cell(r,3).value}":
        (idws.cell(r,5).value or 0)+(idws.cell(r,6).value or 0) for r in range(2,11)}
panelF = {"CoRT": tot, "LF": lf_n, "ID": id_n}

# ---------- eFigure 1: CoRT coverage grid ----------
res = pd.read_csv("results_all_pooled.csv")
notr = pd.read_csv("results_not_estimable.csv")
COMPS = ["rigid v non-rigid","rigid v soft mesh","rigid v rewiring",
         "soft mesh v flap alone","rewiring v flap alone","single v dual flap",
         "muscle flap v omentum","pPM v pGO","pPM v pLD","pPM v pRA",
         "pedicled v free","pPM v pPM + pGO"]
STRATA = ["pooled","oncological","cardiac","infection"]
OUTCOMES = ["Infx [Wound]","Infx [Prosthetic]","Dehiscience","CW Instability",
            "Necrosis","Flap Loss","Seroma","Hematoma","Hernia","Vasc Comp",
            "Impaired Pulm Fxn","<30 Mortality","Mortality","Reoperation",
            "Readmission","LOS","Op Time"]
grid = {}
rc = res[res.stream == "CoRT"]
for _, r in rc.iterrows():
    grid[(r.comparison_name, r.subgroup, r.outcome_name)] = {
        "k": int(r.n_studies), "n": int(r.total_patients),
        "sig": bool(float(r.p_effect) < 0.05)}
raw = pd.read_csv("meta_analysis_data.csv")
for (comp, sub, out), g in raw.groupby(["comparison","subgroup_category","outcome"]):
    key = (comp, sub, out)
    if key not in grid:
        grid[key] = {"k": int(g.study_name.nunique()),
                     "n": int(g.n.sum()), "sig": False}
efig = [{"comparison": c, "stratum": s, "outcome": o,
         **grid.get((c,s,o), {"k":0,"n":0,"sig":False})}
        for c in COMPS for s in STRATA for o in OUTCOMES]


# ---------- panels G/H: country and population, from the extraction workbook ----------
_q = json.load(open("qual_data.json"))
_ind = {"infection": "infection", "oncological": "oncological",
        "cardiac": "cardiac", "mixed": "mixed"}
panelG = {"countries": dict(Counter(x["country"] for x in _q).most_common())}
_pbi = {}
for x in _q:
    _pbi.setdefault(_ind[x["ind"]], Counter())[x["pop"]] += 1
panelH = {"population_by_indication": {k: dict(v) for k, v in _pbi.items()},
          "population_total": dict(Counter(x["pop"] for x in _q))}

json.dump({"panelA":panelA,"panelB":panelB,"panelC":panelC,"panelD":panelD,
           "panelE":panelE,"panelF":panelF,"panelG":panelG,"panelH":panelH},
          open("fig3_data.json","w"), indent=1)
json.dump({"comparisons":COMPS,"strata":STRATA,"outcomes":OUTCOMES,"cells":efig},
          open("efig1_data.json","w"), indent=1)
print("panelA bins:", len(panelA))
print("panelB:", panelB)
print("panelC flaps:", list(panelC["flaps"])[:8], "rewiring:", panelC["rewiring_studies"])
print("panelD:", panelD)
print("panelE:", panelE)
print("panelF sizes:", {k: len(v) for k,v in panelF.items()})
print("panelG countries:", len(panelG["countries"]), panelG["countries"])
print("panelH:", panelH)
print("efig cells:", len(efig))
