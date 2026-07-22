# Hotmaps industrial heat load profiles

Pulled from Hotmaps GitLab (`hotmaps/load_profile/*`), Task 2.7.

## Continuous HT industry (definition)

**Continuous high-temperature (HT) industry** = plants whose process heat is:

1. **High temperature** — typically ≫200 °C (kilns, furnaces, crackers, melting), so heat pumps don’t apply and the model uses resistive / IHB (COP ≈ 1); and  
2. **Continuous / baseload** — runs ~24/7 with little diurnal swing (not shift-based daytime-only load).

In this project that is mainly: steam crackers, iron & steel, cement/lime, much of chemicals and glass. Food and textiles are more often lower-T and/or shift-driven.

## What was downloaded

| Folder | Content |
|--------|---------|
| `yearlong_2018/*.csv` | Ready-to-use **8760-h** profiles by `NUTS0_code` × Hotmaps process (calendar 2018) |
| `*_generic/` | Typical-day building blocks (month × daytype × hour) |
| `sector_mapping.csv` | Climate TRACE `subsector` → Hotmaps `process` |
| `profile_flatness_summary.csv` | How flat DE profiles are (CV ~1–2%) |

Source repos (generic + yearlong 2018): iron_and_steel, chemicals_and_petrochemicals, paper, food_and_tobacco, non_metalic_minerals (Hotmaps spelling).

## Sector match to this project

| Climate TRACE `subsector` | Hotmaps process | Notes |
|---------------------------|-----------------|-------|
| iron-and-steel | iron_and_steel | direct |
| pulp-and-paper | paper | direct |
| food-beverage-tobacco | food_and_tobacco | direct |
| chemicals | chemicals_and_petrochemicals | direct |
| petrochemical-steam-cracking | chemicals_and_petrochemicals | proxy |
| cement, lime, glass | non_metalic_minerals | shared NMM profile |
| aluminum, other-metals, textiles | — | no Hotmaps industry profile → keep flat |

~**495 / 522 TWh** (95%) of fleet replaceable heat has a Hotmaps sector profile.

Country code: Hotmaps uses **EL** for Greece (map `GRC`→`EL`, not `GR`). UK may appear as `UK`.

## Flatness (why profiles may not change ≥90% much)

For Germany 2018 yearlong series, day/night load ratio ≈ **1.02** and CV ≈ **1–2%** for all five Hotmaps industry processes — essentially flat. That supports keeping a flat load for continuous HT sites.

## You do **not** need to pull these yourself

Data are already under `Input/hotmaps_load_profiles/`. Wiring them into `run_multiband_potential.py` (replace flat `load_b` with normalized hourly shapes) is a separate code change if you want a sensitivity run.
