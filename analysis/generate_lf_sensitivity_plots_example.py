import os, sys
# import the library sitting next to this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from revman_forest_lib import revman_forest

# write outputs next to this script unless OUT is overridden
OUT = os.environ.get("OUT", os.path.dirname(os.path.abspath(__file__)))

# ==========================================================
# FEV1% | outlier exclusion of Zhao 2017 (r = 0.74)   k=4 -> Random
# ==========================================================
revman_forest(
    title_bar_text="LF Post vs Pre (Paired-Correlation Model)  |  Outcome: FEV1% (Sensitivity Analysis excluding Zhao 2017, r = 0.74)",
    data_type="continuous", groupA_name="Post", groupB_name="Pre",
    effect_name="Mean Difference", method_name="IV, Random, 95% CI",
    rows=[
        dict(name="Kohman 1991",  mA=79.0, sA=21.0, nA=17, mB=78.1, sB=22.4, nB=17,
             weight=14.9, est=0.90,  lo=-6.56,  hi=8.36),
        dict(name="Luezzi 2014",  mA=82.3, sA=23.0, nA=39, mB=87.1, sB=18.9, nB=39,
             weight=27.9, est=-4.80, lo=-9.69,  hi=0.09),
        dict(name="Meadows 1985", mA=83.0, sA=15.7, nA=6,  mB=92.0, sB=18.5, nB=6,
             weight=8.9,  est=-9.00, lo=-19.09, hi=1.09),
        dict(name="Bae 2024",     mA=91.6, sA=13.0, nA=35, mB=98.6, sB=9.0,  nB=35,
             weight=48.3, est=-7.00, lo=-9.90,  hi=-4.10),
    ],
    total_est=-5.39, total_lo=-8.58, total_hi=-2.19, total_nA=97, total_nB=97,
    het_lines=[
        "Heterogeneity: Tau\u00b2 = 3.31; Chi\u00b2 = 4.30, df = 3 (P = 0.23); I\u00b2 = 30%",
        "Test for overall effect: Z = 3.30 (P = 0.001)",
        "95% Prediction interval: [\u221215.90, 5.12]",
    ],
    footnotes=[],
    xlim=(-22.5, 11.5), xticks=[-20,-15,-10,-5,0,5,10],
    favors_left="Favours [Pre]", favors_right="Favours [Post]",
    log_scale=False,
    out_png=f"{OUT}/rev2_LF_Paired_FEV1pct_SENS_exclZhao.png",
    out_pdf=f"{OUT}/rev2_LF_Paired_FEV1pct_SENS_exclZhao.pdf",
)

# ==========================================================
# FVC% | outlier exclusion of Zhao 2017 (r = 0.65)   k=4 -> Random
# ==========================================================
revman_forest(
    title_bar_text="LF Post vs Pre (Paired-Correlation Model)  |  Outcome: FVC% (Sensitivity Analysis excluding Zhao 2017, r = 0.65)",
    data_type="continuous", groupA_name="Post", groupB_name="Pre",
    effect_name="Mean Difference", method_name="IV, Random, 95% CI",
    rows=[
        dict(name="Kohman 1991",  mA=80.3, sA=17.5, nA=17, mB=78.1, sB=20.1, nB=17,
             weight=22.1, est=2.20,   lo=-5.36,  hi=9.76),
        dict(name="Luezzi 2014",  mA=82.0, sA=21.6, nA=39, mB=94.1, sB=19.3, nB=39,
             weight=28.3, est=-12.10, lo=-17.51, hi=-6.69),
        dict(name="Meadows 1985", mA=83.8, sA=15.5, nA=6,  mB=88.5, sB=18.6, nB=6,
             weight=13.7, est=-4.70,  lo=-16.33, hi=6.93),
        dict(name="Bae 2024",     mA=90.3, sA=9.6,  nA=35, mB=98.2, sB=10.7, nB=35,
             weight=35.9, est=-7.90,  lo=-10.73, hi=-5.07),
    ],
    total_est=-6.42, total_lo=-11.73, total_hi=-1.11, total_nA=97, total_nB=97,
    het_lines=[
        "Heterogeneity: Tau\u00b2 = 18.33; Chi\u00b2 = 9.39, df = 3 (P = 0.02); I\u00b2 = 68%",
        "Test for overall effect: Z = 2.37 (P = 0.02)",
        "95% Prediction interval: [\u221228.22, 15.38]",
    ],
    footnotes=[],
    xlim=(-21.5, 13.5), xticks=[-20,-15,-10,-5,0,5,10],
    favors_left="Favours [Pre]", favors_right="Favours [Post]",
    log_scale=False,
    out_png=f"{OUT}/rev2_LF_Paired_FVCpct_SENS_exclZhao.png",
    out_pdf=f"{OUT}/rev2_LF_Paired_FVCpct_SENS_exclZhao.pdf",
)

print("done")
