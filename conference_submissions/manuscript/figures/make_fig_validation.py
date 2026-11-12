"""Fig: bottom-up heat (total and fossil/replaceable) vs JRC-IDEES useful heat, EU-27 by sector."""
import pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
ROOT="/Users/annayuen/Desktop/IECC/industrial_decarb/facility_IHB_potential/"
ref=pd.read_csv(ROOT+"heat_demand/analysis_outputs/heat_by_country_comparison.csv").groupby("sector").reference_twh.sum()
ours=pd.read_csv(ROOT+"heat_demand/analysis_outputs/heat_total_vs_fossil_by_sector.csv").set_index("sector").drop("TOTAL")
df=ours.join(ref).sort_values("reference_twh")
y=np.arange(len(df)); h=0.27
fig,ax=plt.subplots(figsize=(7,4.2))
ax.barh(y+h,df.reference_twh,h,color="#1baf7a",label="JRC-IDEES useful heat (reference)")
ax.barh(y,df.total_twh,h,color="#9bb9e8",label="This study: all fuels")
ax.barh(y-h,df.fossil_twh,h,color="#2a78d6",label="This study: fossil-fired (replaceable)")
ax.set_yticks(y); ax.set_yticklabels(df.index); ax.set_xlabel("Process heat (TWh$_{th}$/yr)")
ax.legend(frameon=False,fontsize=8,loc="lower right"); ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
for e in("pdf","png"): plt.savefig(ROOT+f"conference_submissions/manuscript/figures/fig_heat_validation.{e}",dpi=300)
print(df.round(1).assign(ratio_fossil=(df.fossil_twh/df.reference_twh).round(2),ratio_total=(df.total_twh/df.reference_twh).round(2)))
