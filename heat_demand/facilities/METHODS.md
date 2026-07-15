# Facility Production & Heat Demand — Methods and Assumptions

This documents the data pipeline in `heat_demand/facilities/` and every
emission factor and specific energy consumption (SEC) value it uses.
**Keep this file in sync with the parameter tables in
`merge_production.py`.**

Pipeline (run in order):

1. `export_facilities_2024.py` — exports EU manufacturing facilities from
   `Input/facility_master_2024_v6.csv` (Climate TRACE, updated production
   capacities) → `facilities_2024_eu.csv`.
2. `combine_hotmaps_2014.py` — matches them against Fraunhofer hotmaps
   `Input/Industrial_Database_2014.csv` → `facilities_matched_hotmaps_2014.csv`.
3. `merge_production.py` — picks a production value per facility, adds
   heat estimates → `facilities_2024_eu_merged.csv` / `.xlsx`.
4. `heat_temperature_bands.py` — splits heat demand into temperature bands
   using `Input/industryBenchmarks_2014.csv` →
   `facilities_2024_eu_heat_bands.csv` / `.xlsx`.
5. `apply_dedup.py` — executes the reviewed duplicate-site decisions
   (`../analysis_outputs/duplicate_sites_flagged.csv`: 72 deletions, the
   Ardagh Barnsley merge, sourced capacity corrections) →
   `facilities_2024_eu_deduplicated.csv` / `.xlsx` (**use this file for
   analysis**).

## 0. Climate TRACE data cleaning

Deduplicate facilities by identical names, identical coordinates, identical capacity/heat values (near-impossible by coincidence), known ownership renames, and known single-mill locations.
Row-level decisions (which source_id to delete, with sources validating the
true capacity) are in `../analysis_outputs/duplicate_sites_flagged.csv` —
72 rows deleted across 69 groups; the cleaned dataset is
`facilities_2024_eu_deduplicated.csv` / `.xlsx`. Review-flagged rows were
resolved against the bottom-up vs top-down sector comparison: over-counted
sectors (food) lean delete, under-counted sectors (glass, non-ferrous) lean
keep — the Ardagh Barnsley pair was merged (heats summed) rather than
dropped, and the uncertain Ferropem/Ferroglobe rows were kept. Beware: identical
capacity/production values are often the country-default artifact (§6),
not duplication evidence — e.g. Laakirchen vs Steyrermühl are two real
mills that share the Austrian default 338 kt.

Fill in food_beverage, glass and textiles industry production values

## 1. Facility matching (Climate TRACE ↔ hotmaps)

No shared facility ID exists, so matching is spatial, blocked by industry,
validated by name:

- **Subsector crosswalk** between the two taxonomies (e.g. `pulp-and-paper`
  ↔ "Paper and printing", `lime` ↔ "Non-metallic mineral products").
- **Spatial join**: haversine distance between Climate TRACE lat/lon and the
  hotmaps WKT point; candidate pairs within 5 km, assigned greedily
  nearest-first, one-to-one. 515 hotmaps rows lack coordinates and can
  never match.
- **Name validation**: difflib ratio on normalized names (legal suffixes
  stripped). Confidence: **high** ≤ 1 km; **medium** 1–5 km with name
  similarity ≥ 0.4; **low** 1–5 km on location alone.

## 2. Production source selection (`production_source`, `data_tier`)

| Tier | Source | Rule |
|---|---|---|
| 1 | `climate_trace` (2024) | Default: `annual_output_t = capacity × capacity_factor` from the facility master. |
| 2 | `hotmaps` (2014) | Replaces tier 1 when the Climate TRACE value is a **country-level artifact** (identical output duplicated across facilities within one country + subsector) and a high/medium-confidence match reports 2014 production; also fills sectors where Climate TRACE has no capacity (glass). |
| 3 | none — heat only | No production in either source; heat estimated directly from emissions (section 3). |

Low-confidence (location-only) matches are never used. `production_year`
records the vintage — mind the 2014 vs 2024 gap. `ct_country_artifact`
flags duplicated Climate TRACE values that could not be replaced
(63 facilities, mostly lime and pulp-and-paper).

## 3. Emissions → heat inversion (`heat_method = emissions_fuel_inversion`)

For subsectors with no production data whose CO2e is ~100% fuel combustion
and whose heat is boiler-dominated (steam / hot water, mostly < 200 °C):

```
fuel_energy_TJ  = CO2e_t × combustion_share ÷ fuel_EF (tCO2/TJ)
useful_heat_TJ  = fuel_energy_TJ × boiler_efficiency
```

| Subsector | combustion share | fuel EF (tCO₂/TJ) | boiler eff. |
|---|---|---|---|
| food-beverage-tobacco | 1.0 | 61.4 | 0.85 |
| textiles-leather-apparel | 1.0 | 61.4 | 0.85 |

**Food country rescaling** (applied after the inversion, factor recorded in
`food_country_scale`): Climate TRACE food emissions are modeled and badly
mis-allocated between countries (Portugal ~20× too high, Spain ~2.6×), so
they are used **only as within-country allocation weights**. Each country's
food heat total is scaled to the useful-energy reference
(`References/industry_useful_energy_demand_<CC>.csv`, non-electric process
heat + steam rows). GBR has no reference file and uses the aggregate EU-26
factor. Consequence: food facility values are downscaled country by country
(EU food total ≈ 103 TWh, the reference level, ≈54% of the Eurostat ×
heat-share yardstick); the earlier EU-wide combustion-share calibration is
superseded and the share is back at the physical 1.0.

Sources:
- **Fuel emission factors**: IPCC 2006 Guidelines, Vol. 2, Table 2.3 —
  natural gas 56.1 tCO₂/TJ, residual fuel oil 77.4 tCO₂/TJ. The 61.4 value
  is a 75% gas / 25% oil mix, consistent with the fuel-share assumptions in
  `estimating_heat_demand.md` and the gas-dominated mix reported for these
  sectors in JRC-IDEES.
- **Combustion share 1.0**: food and textile processing have no process
  CO₂ — reported emissions are boiler/oven/dryer fuel. For food the level
  is then reset by the country rescaling above; textiles is left unscaled
  because it already matches the top-downs (~97% of Eurostat × heat share).
- **Boiler efficiency 0.85**: typical industrial steam boiler (US DOE
  steam system guidance).

**Not valid** for cement/lime (60–65% of CO₂ is calcination, not fuel —
IEA Cement Roadmap 2018 / EuLA) or iron-and-steel (reductant vs. fuel
emissions inseparable) without sector-specific combustion-share
corrections.

## 4. Production × SEC (`heat_method = production_sec`)

For tier-1/2 facilities: `fuel_energy_TJ = production_t × SEC ÷ 1000`,
`useful_heat_TJ = fuel_energy_TJ × eff`. SEC is **fuel input for process
heat, GJ per tonne of the product named by `capacity_units`**; `eff` is the
process's **useful thermal efficiency** — useful heat delivered to the
process ÷ fuel input.

**Efficiencies are independent engineering-literature values, not derived
from the JRC-IDEES / IndustryHeat-EU useful-energy reference we validate
against**, so the reconciliation stays non-circular. Earlier revisions set
`eff = 1.0` for direct-fired kilns (the hotmaps fuel-accounting convention,
which reports fuel *consumed* rather than useful heat *delivered*); this
made kiln sectors read 150–200% of a useful-energy benchmark and — more
importantly — would oversize an electrified replacement, which only has to
supply the useful heat. Each `eff` below is now a sourced furnace or boiler
efficiency. The remaining bracket is physical: useful heat sits below fuel
input (this table) and below Eurostat *final* energy, and near the
JRC-IDEES *useful*-energy reference.

| Subsector (product) | source_type | SEC (GJ/t) | eff | Basis (SEC ‖ efficiency) |
|---|---|---|---|---|
| cement (t cement) | all | 2.8 | **0.60** | SEC: ~3.5 GJ/t clinker thermal (IEA/CSI GNR, IEA Cement Roadmap 2018) × ~0.77 EU clinker-to-cement ratio (Cembureau). **eff:** cement pyroprocessing first-law efficiency 50–60% (Madlool et al. 2011, *Renew. Sustain. Energy Rev.* 15:2042); losses are hot clinker, calcination-CO₂ exhaust, shell radiation |
| lime (t lime) | all | 4.5 | **0.65** | SEC: EU average across kiln types, 3.6–7.5 GJ/t (EuLA; EU BREF Cement/Lime/MgO). **eff:** EU mix of shaft (~0.80) and rotary (~0.55) lime kilns (BREF) |
| glass (t glass) | all | 6.5 | **0.45** | SEC: EU average melting + working energy (Schmitz et al. 2011, *Energy consumption and CO₂ emissions of the European glass industry*). **eff:** glass melting-furnace efficiency 40–50%, high flue + structural loss (Beerkens 2008; Schmitz et al. 2011) |
| pulp-and-paper (t pulp & paper) | all | 10.5 | 0.85 | SEC: CEPI Key Statistics, heat use per tonne produced; **~60% biomass-supplied** (black liquor). **eff:** industrial steam boiler (US DOE) |
| steam cracking (t ethylene) | all | 35.9 | **0.90** | SEC: **total cracking-furnace duty** (external fuel + byproduct fuel-gas firing), hotmaps benchmark — chosen over 17.0 GJ/t external-fuel-only (Ren et al. 2006) because an electrified furnace must supply the whole duty (byproduct CH₄/H₂ tail gas is fossil and must also be decarbonized); reproduces IndustryHeat-EU per-facility values. **eff:** fired heater with strong convection heat recovery, high useful fraction (Ren, Patel & Blok 2006, *Energy* 31:425; Ullmann's *Ethylene*) — **least-certain efficiency** |
| iron-and-steel (t crude steel) | BF/BOF, BOF | 4.8 | **0.70** | SEC: **final-consumption scope** — sinter (1.20 t × 2.24 GJ/t) + rolling (0.90 t × 2.39 GJ/t), hotmaps; coke ovens + blast furnaces excluded (Eurostat transformation sector). **eff:** reheating/sinter furnaces w/ recuperation, 65–75% (IEA Iron & Steel; worldsteel) |
| | EAF | 2.5 | **0.70** | Fuel only (NG burners + reheating furnace); electricity excluded |
| | DRI-EAF | 12.0 | **0.70** | NG for DRI (~10 GJ/t DRI) + EAF fuel; DRI gas kept (industry final consumption) |
| | mixed routes | 3.7–8.4 | **0.70** | Averages of the constituent routes |
| chemicals | ammonia (t NH₃) | 9.0 | **0.90** | SEC: reformer **fuel** share only; feedstock gas (~18 GJ/t) excluded (IEA Ammonia Technology Roadmap 2021). **eff:** primary reformer fired heater w/ heat recovery |
| | soda_ash (t) | 10.0 | 0.85 | Solvay process steam + kilns (EU BREF LVIC); boiler-led |
| | methanol (t) | 9.0 | **0.90** | Fuel share only, feedstock excluded (IEA/IRENA); reformer fired heater |
| aluminum | Refinery (t alumina) | 11.0 | 0.85 | Bayer digestion/calcination steam (IAI / IEA); boiler-led |
| | Smelting (t aluminum) | 3.0 | **0.65** | Anode baking + cast-house fired furnaces; smelting electricity excluded (IAI) |

**Note on `eff` and electrification.** These efficiencies convert fuel input
to the *useful heat the process needs*, which is the correct demand basis for
sizing an electrified replacement. They are **not** the electricity-to-heat
efficiency of the replacement technology (heat-pump COP, resistive/IHB
delivery, ~0.9–0.95), which is applied separately in the LCOH model. The
gas-vs-electric crossover is governed by the *ratio* of the two, which is
modest at high temperature — electric heating mainly avoids the combustion
flue-gas loss, not the process-inherent losses (hot product, off-gas). The
steam-cracking efficiency (0.90) is the least certain and warrants a
sensitivity run.

## 5. Temperature bands (`heat_temperature_bands.py`)

Heat demand is split into five bands (<100 °C, 100–200, 200–500,
500–1000, >1000 °C) using the **hotmaps industry benchmarks**
(`Input/industryBenchmarks_2014.csv`; Fraunhofer ISI, per-process fuel
SECs and band shares with literature sources — Fleiter et al., Arens et
al., Rehfeldt et al., McKenna, and others cited in the file itself).

Each facility maps to a **recipe** of benchmark processes
(weight = t process throughput per t product). For tier-1/2 facilities,
banded heat = `production_t × Σ(weight × SEC_Fuels × band_share)`
(`bench_heat_tj` — note this benchmark-based heat can differ from the
section-4 estimate for the remaining sectors; petrochemical now agrees,
since section 4 adopts the benchmark 35.9 GJ/t total-furnace basis
(external fuel + byproduct fuel-gas firing) rather than 17 GJ/t external
fuel — see the steam-cracking note in section 4). For tier-3 facilities the band shares are applied to the
emissions-derived `useful_heat_tj`.

| Facility type | Recipe (process × weight) | Basis |
|---|---|---|
| cement | Clinker calcination-dry × 0.77 | EU clinker ratio (Cembureau); dry kilns dominant |
| lime | Lime burning × 1.0 | |
| glass | Container × 0.55, Flat × 0.30, Fiber × 0.05, Other × 0.10 | EU production mix (FEVE / Glass Alliance Europe) |
| steel BF/BOF, BOF | Sinter × 1.20, Rolled steel × 0.90 | Coke oven (0.30) and Blast furnace (0.95) excluded — Eurostat transformation sector (see §4); band shares now come from sinter + reheating/rolling only |
| steel EAF | EAF × 1.0, Rolled steel × 0.90 | |
| steel DRI-EAF | Direct reduction × 1.0, EAF × 1.0, Rolled × 0.90 | |
| steel mixed routes | average of constituent recipes | |
| ammonia / soda ash / methanol | matching Basic chemicals process × 1.0 | |
| steam cracking | Ethylene × 1.0 | |
| aluminum Smelting | Aluminum primary × 1.0 | |
| pulp & paper | Paper × 0.5 + pulp mix × 0.5; pulp split by source_type keywords (chemical/mechanical), "Pulp misc." → 70/30 chem/mech (CEPI EU mix) | coarse — the corrected workbook is authoritative for this sector |
| food (tier 3) | band shares: equal-weight blend of Sugar, Dairy, Brewing, Meat, Bread & bakery, Starch | source_type is generic for 880/886 sites |

**External band splits** (processes missing from the benchmarks;
`band_source = external`):

- **Alumina refinery**: 75% at 100–200 °C (Bayer digestion steam), 25% at
  500–1000 °C (calcination) — IAI Bayer process data.
- **Textiles**: 55% <100 °C, 35% 100–200 °C, 10% 200–500 °C — dyeing /
  finishing hot water and steam (Rehfeldt et al. 2018).

Mechanical pulp has a negative fuel SEC in the benchmarks (net heat
producer); it is clamped to zero so recipes never subtract heat.
Band shares per process are normalized to sum to 1.

## 6. Known caveats

- **Climate TRACE country artifacts**: identical `annual_output_t`
  duplicated across facilities (89 found; 26 replaced by hotmaps, 63
  flagged). Per-facility values in lime and pulp-and-paper are the most
  affected.
- **Climate TRACE food/textile emissions are modeled** and some sites are
  implausible (e.g. a brewery at 1.14 MtCO₂e; Portugal's median food site
  4× France's). Trust tier-3 heat in aggregate and for ranking; screen
  sites > ~200 ktCO₂e before plant-level use.
- **Hotmaps circularity**: hotmaps production was itself partly
  back-calculated from ETS emissions via sector benchmarks, and its
  values are **2014 vintage** used against 2024 facilities.
- **Pulp-and-paper biomass**: `useful_heat` is total process heat;
  only ~40% is fossil-fired in the EU (Rahnama Mobarakeh et al. 2021),
  so fossil-replaceable heat is ~0.4 × the reported value.
- **Iron & steel is now final-consumption scope only** (sinter + rolling):
  bottom-up covers ~54% of the Eurostat top-down. The gap is real
  final-consumption fuel not in the recipe — BOF shop, casting, and
  coke-oven/blast-furnace gas fired in downstream furnaces. Raising the
  BF/BOF SEC toward ~7–9 GJ/t would close it; 4.8 is the defensible
  benchmark-derived floor.
- **Electricity is excluded everywhere** (EAF power, smelting power,
  glass electric boosting): these columns are fuel-based heat only.
- **No estimate possible** (blank heat columns): other-metals (49),
  glass without a hotmaps match (204), 2 steam crackers without capacity.
