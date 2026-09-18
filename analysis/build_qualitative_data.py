#!/usr/bin/env python3
"""Assemble the qualitative reporting dataset: disclosures, radiotherapy,
antibiotics, obesity, population and country, joined to indication and to
whether the study used rigid plating."""
import json, re, openpyxl
from collections import Counter, defaultdict

wb = openpyxl.load_workbook("qual_source.xlsx")
ws = wb["Data"]
col = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1)}
def g(r, name): return ws.cell(r, col[name]).value

IND = {"Infection": "infection", "Oncological": "oncological",
       "Prophylactic": "cardiac", "Mixed": "mixed", "Pooled": "mixed"}

# which studies used a rigid prosthesis, from the CoRT raw sheet
mw = openpyxl.load_workbook("master.xlsx")
rd = mw["CoRT Raw Data"]
tokens = defaultdict(set)
for r in range(2, rd.max_row + 1):
    rec = rd.cell(r, 6).value
    if rec in (None, ""): continue
    key = f"{str(rd.cell(r,2).value).strip()} {rd.cell(r,3).value}"
    tokens[key] |= {t.strip() for t in str(rec).split(",") if t.strip()}
MESH = {"synmesh", "biomesh", "semisyn"}
plating = {k for k, t in tokens.items() if "pros" in t}
meshonly = {k for k, t in tokens.items() if (t & MESH) and "pros" not in t}

import unicodedata
def _ascii(t):
    t = unicodedata.normalize("NFKD", str(t))
    return "".join(c for c in t if not unicodedata.combining(c)).strip().lower()
# Country now lives in the extraction workbook itself (column H).

def frac(v):
    """'14/19' -> (14,19); 'some/194' -> ('some',194); 'NR'/None -> None."""
    if v in (None, "", "NR"): return None
    s = str(v).strip()
    m = re.fullmatch(r"(some|\d+)\s*/\s*(\d+)", s)
    if m:
        num = m.group(1)
        return (None if num == "some" else int(num), int(m.group(2)))
    return "flag"          # 'yes' / 'no' / 'partial ...' etc.

rows = []
for r in range(2, ws.max_row + 1):
    name = str(g(r, "Author")).strip(); yr = g(r, "Year")
    key = f"{name} {yr}"
    rows.append(dict(
        study=key, ind=IND[g(r, "Category")], pop=g(r, "Population"),
        disc=g(r, "Financial disclosure"), tie=g(r, "Industry tie"),
        preRT=g(r, "Preop RT"), postRT=g(r, "Postop RT"),
        preabx=g(r, "Preop abx"), intraabx=g(r, "Intraop abx"),
        postabx=g(r, "Postop abx"), obese=g(r, "Obese"),
        country=g(r, "Country") or "NR",
        plating=key in plating, meshonly=key in meshonly))

missing = [x["study"] for x in rows if x["country"] == "NR"]
print("country unmatched:", missing or "none")

def reported(v): return v not in (None, "", "NR")

# ── disclosures, by whether the study used rigid plating ──────────────
print("\n=== FINANCIAL DISCLOSURE, by construct ===")
for label, sel in (("rigid plating", lambda x: x["plating"]),
                   ("soft mesh only", lambda x: x["meshonly"]),
                   ("no exogenous material", lambda x: not x["plating"] and not x["meshonly"])):
    s = [x for x in rows if sel(x)]
    if not s: continue
    d = Counter(x["disc"] for x in s)
    ind = sum(1 for x in s if x["tie"] not in (None, "NR", "none", "non-industry"))
    print(f"  {label:24} n={len(s):3}  disclosed={d.get('yes',0):3}  "
          f"none declared={d.get('none declared',0):3}  not reported={d.get('NR',0):3}  "
          f"industry tie={ind}")
print("\n  named industry ties among plating studies:")
for x in sorted(rows, key=lambda z: z["study"]):
    if x["plating"] and x["tie"] not in (None, "NR", "none", "non-industry"):
        print(f"     {x['study']:24} {x['ind']:11} {x['tie']}")

# ── radiotherapy in oncological studies ───────────────────────────────
onc = [x for x in rows if x["ind"] == "oncological"]
print(f"\n=== RADIOTHERAPY, oncological studies (n={len(onc)}) ===")
for field, lab in (("preRT", "preoperative RT"), ("postRT", "postoperative RT")):
    rep = [x for x in onc if reported(x[field])]
    print(f"  {lab:18} reported by {len(rep):2}/{len(onc)} ({len(rep)/len(onc)*100:.0f}%), "
          f"not reported by {len(onc)-len(rep)}")
    exact, patients_rt, patients_tot = [], 0, 0
    for x in rep:
        f = frac(x[field])
        if isinstance(f, tuple):
            n, d = f
            if n is not None:
                exact.append((x["study"], n, d, n / d))
                patients_rt += n; patients_tot += d
            else:
                print(f"       {x['study']:22} some/{d} (numerator not reported)")
    for st, n, d, p in sorted(exact, key=lambda z: -z[3]):
        print(f"       {st:22} {n}/{d} ({p*100:.0f}%)")
    if patients_tot:
        print(f"       pooled across studies giving a numerator: "
              f"{patients_rt}/{patients_tot} ({patients_rt/patients_tot*100:.1f}%)")
neither = [x for x in onc if not reported(x["preRT"]) and not reported(x["postRT"])]
both = [x for x in onc if reported(x["preRT"]) and reported(x["postRT"])]
print(f"  neither reported: {len(neither)}/{len(onc)}   both reported: {len(both)}/{len(onc)}")

# ── antibiotics, obesity, population ──────────────────────────────────
print("\n=== OTHER REPORTING, all 103 studies ===")
for field, lab in (("preabx", "preoperative antibiotics"), ("intraabx", "intraoperative antibiotics"),
                   ("postabx", "postoperative antibiotics"), ("obese", "obesity / BMI")):
    rep = sum(1 for x in rows if reported(x[field]))
    print(f"  {lab:28} reported by {rep:3}/103 ({rep/103*100:.0f}%)")
    for ind in ("infection", "oncological", "cardiac", "mixed"):
        s = [x for x in rows if x["ind"] == ind]
        n = sum(1 for x in s if reported(x[field]))
        print(f"       {ind:12} {n:2}/{len(s):2}")
print("\n  population:", Counter(x["pop"] for x in rows))
print("  by indication:")
for ind in ("infection", "oncological", "cardiac", "mixed"):
    s = [x for x in rows if x["ind"] == ind]
    print(f"     {ind:12} {Counter(x['pop'] for x in s)}")
print("\n  countries:", Counter(x["country"] for x in rows).most_common())

json.dump(rows, open("qual_data.json", "w"), indent=1)
print("\nwrote qual_data.json")
