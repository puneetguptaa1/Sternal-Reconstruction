"""Render the ID infection-restricted mortality forest even though it is not
significant — it is the co-primary comparison for the pooled estimate and must
appear beside it in Figure 5E."""
import os, openpyxl
os.environ.pop("MA_NO_PLOTS", None)
import meta_analysis_pipeline as mp
import run_lf_id_meta as r

mp.NO_PLOTS = False
mp.OUTPUT_DIR = "output_ID"
wb = openpyxl.load_workbook("master.xlsx", read_only=True, data_only=True)
rows = list(wb["ID Raw Data"].iter_rows(values_only=True))[1:]
wb.close()

studies = r._stratum(r.build_id(rows, (6, 7)), "infection")
res, classified = r.analyse(studies, False)
mp.make_forest_plot(res, "ID Immediate vs Delayed", "infection", "Mortality",
                    "Immediate", "Delayed")
print(f"rendered ID infection mortality: k={res['k']} OR={res['OR_pooled']:.2f} "
      f"p={res['p_effect']:.4f} I2={res['I2']:.0f}%")
