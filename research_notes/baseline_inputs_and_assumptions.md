# Baseline run: inputs and assumptions (no land price)

Compiled 2026-11-05 from the code and input files. This documents the baseline as it is currently implemented; it is not a design proposal. Items marked **DECIDE** or **CHECK** are unresolved and affect how firm the numbers are.

## 1. Baseline run definition

| Item | Value | Source |
|---|---|---|
| Scenario folders | `outputs/multiband/land_5km_ss_2030_liion/` (primary), `land_15km_ss_2030_liion/` (sensitivity) | outputs/multiband/README.md |
| Command | `python run_multiband_potential.py --scenario land_5km_ss_2030_liion --project-start 2030` (15 km adds `--land-csv land_availability/outputs/land_availability_by_facility_15km.csv`) | README |
| Run date | by_facility.csv written 2026-10-26 16:58, one minute after the COP change (16:57), so it reflects Rissman COPs 3.7/2.2. run_log.txt was not refreshed (still 07-24) | file mtimes |
| Fleet | 2,192 facilities, 27 countries, 522.3 TWh/yr replaceable heat, all status `ok` | by_facility.csv |
| Heat case | base (low/high = 389/703 TWh) | HEAT_BOUNDS_LOGIC.md |
| Cost year | 2030 (BNEF 2030 PV + Li-ion; EI/Rissman costs inflated to 2030 USD) | CONFIG `project_start` |
| Land price | none. Land is a hard cap only (50 MWdc/km² × available km²) | solver `max_solar_mw` |

Baseline outputs, recomputed 2026-11-05 from the current by_facility.csv (pre-VOM, Rissman COPs). The run_log.txt files in these folders are dated 2026-07-24 and are STALE; do not quote them.

| Land buffer | Sites meeting 90% | Share of heat | HW LCOH_served (≥90% cohort) | HW LCOH_served (all served MWh) | HW reliability |
|---|---|---|---|---|---|
| 5 km | 1,939 / 2,192 | 40.7% | $65.1/MWh | $62.2/MWh | 59% |
| 15 km | 2,150 / 2,192 | 74.9% | $80.9/MWh | $83.0/MWh | 86% |

("HW" means heat-weighted.)

## 2. Heat demand inputs

- **Facilities:** Climate TRACE 2024 facility master (`Input/facility_master_2024_v6.csv`), EU manufacturing, deduplicated (72 rows deleted, Ardagh Barnsley merged). Final file: `heat_demand/facilities/facilities_2024_eu_replaceable.csv` (2,415 rows, 2,192 with replaceable heat > 0).
- **Production source tiers:** (1) Climate TRACE capacity × capacity factor. (2) Hotmaps 2014 production where Climate TRACE is a country-level artifact (tier 2 is 2014 vintage). (3) No production: heat is back-calculated from CO2e.
- **Heat formula:** useful heat = production × SEC × η. Replaceable heat = useful heat × fossil share. Electricity is excluded everywhere.
- **SEC (GJ/t) and η:**

| Subsector | SEC | η |
|---|---|---|
| Cement | 2.8 | 0.60 |
| Lime | 4.5 | 0.65 |
| Glass | 6.5 | 0.45 |
| Pulp and paper | 10.5 | 0.85 |
| Steam cracking | 35.9 | 0.90 |
| Iron and steel | 4.8 BF/BOF, 2.5 EAF, 12.0 DRI-EAF | 0.70 |
| Ammonia | 9.0 | 0.90 |
| Soda ash | 10.0 | 0.85 |
| Methanol | 9.0 | 0.90 |
| Alumina | 11.0 | 0.85 |
| Aluminium smelting | 3.0 | 0.65 |

  Full citations are in `heat_demand/facilities/METHODS.md` §4.
- **Food and textiles (no production data):** fuel TJ = CO2e × 1.0 ÷ 58.2 tCO2/TJ; useful heat = fuel × 0.85 boiler efficiency. Food is then rescaled per country to JRC-IDEES-2023 non-electric useful heat (Climate TRACE food emissions are used only as within-country allocation weights). Textiles are not rescaled.
- **Fossil share:** Eurostat `nrg_d_indq` 2024, fossil ÷ (fossil + biomass), by subsector and country. Unreliable slices and GBR fall back to the EU-27 aggregate (311 of 2,415 facilities use `eu27_fallback`). Median fossil shares in the fleet: pulp and paper 0.43, cement and lime 0.84, food 0.91, most others ~1.0.
- **Temperature bands:** <100, 100–200, 200–500, 500–1000, >1000 °C, from Hotmaps `industryBenchmarks_2014.csv` recipes. External splits: alumina refinery 75% at 100–200 °C and 25% at 500–1000 °C; textiles 55% below 100 °C and 45% at 100–200 °C. Band shares are fixed in the low/high cases.
- **Load shape:** flat. Hourly load = replaceable MWh ÷ 8,760, with no diurnal or seasonal shape (`shape24` is all ones). Each band's load is its share of the total.
- **Subsector totals (TWh/yr):** petrochemical cracking 152.3, iron and steel 101.4, food 98.4, cement 54.1, chemicals 43.1, pulp and paper 18.2, textiles 17.7, glass 16.3, lime 10.9, aluminium 10.1.

> **NOTE (to state in methods and limitations): heat demand is NOT projected to 2030.** Costs are 2030 but the heat inventory is a 2024 snapshot (Climate TRACE 2024 production and emissions, Eurostat 2024 fossil shares, some Hotmaps 2014 production). No growth, efficiency, fuel-switching or plant-closure changes are applied between 2024 and 2030. Results are 2030 costs applied to 2024 heat demand.

## 3. Technology mapping and model structure

- **<200 °C bands:** solar → heat pump, with a shared Li-ion battery buffering the electricity. No thermal store.
  - COP 3.7 for <100 °C and 2.2 for 100–200 °C (Rissman 2022 Table 3).
- **≥200 °C bands (COP 1.0):** solar → resistive charge → shared IHB thermal store → process heat.
  - One store serves all IHB bands, and higher-temperature stored heat may serve lower-temperature IHB bands.
- **Solar:** one shared array per site, no grid import, no curtailment cost.
- **Objective:** hard availability floor of 90% on total load. Land-limited sites that cannot reach 90% first maximize served heat, then minimize cost.
- **Unserved heat:** not costed (no VoLL).
- **Time resolution:** 16 representative days from k-means medoids (seed 0) on the 2023 PVGIS daily solar profiles, weighted by cluster size, 24 h each, cyclic state of charge per day. Storage is therefore intra-day only, with no seasonal carry-over.
- **Storage duration cap:** energy ≤ 16 h × discharge power, for both Li-ion and IHB.
- **LCOH_served** = total annualized system cost ÷ served MWh. `LCOH_total` divides by the full load instead.

## 4. Cost inputs (2030 USD)

| Component | CAPEX | FOM | Notes |
|---|---|---|---|
| Solar PV (fixed axis, per kW DC) | BNEF country value; examples: DEU 424.8, GBR 446.2, others ~425–430 | ~$10.3–11.0/kW-yr | `Input/bnef_country_costs.csv` |
| Li-ion (4 h) | BNEF country value; DEU 748.7, GBR 706.0, all others 727.3 $/kW | $6.9–7.3/kW-yr on discharge power | Energy price = $/kW ÷ 4 h. Round-trip efficiency 0.90, applied as √0.90 each way |
| Heat pump, <100 °C | $918.3/kW_th | $15.74/kW_th-yr | Rissman 2022, $700 in 2021 USD × 1.312 |
| Heat pump, 100–200 °C | $1,141.3/kW_th | $23.61/kW_th-yr | Rissman 2022, $870 in 2021 USD × 1.312 |
| IHB power in | $116.66/kW | 0 | Energy Innovation (Rissman & Gimon), $100 in 2023 USD × 1.167 |
| IHB power out | $349.99/kW | 0 | EI, $300 in 2023 USD |
| IHB energy | $5.83/kWh | 0 | EI, $5 in 2023 USD; low and high are $1.75 and $11.67 |
| IHB round-trip efficiency | 0.95 | n/a | Applied as √0.95 each way |

- **Inflation:** US CPI-U, 2021 = 270.970, 2023 = 304.703, 2025 = 321.962, then +2%/yr, so 2030 = 355.472.
- **Annualization:** each item's CAPEX × country CRF, plus FOM. HP lifetime is listed as 25 years in the cost file.
- **CRF:** from IRENA (`crf_source = irena`), taken from the PV row and applied to all components. The code and docs call it the "BNEF CRF", which is inaccurate. 2030 CRF examples: DEU 0.0603, FRA 0.0613, GBR 0.0659, ITA 0.0717, ESP 0.0762, POL 0.0862, IRL 0.0896.
- **BNEF coverage:** see [[methods-writing-tracker]] in the memory directory. Direct PV data exist for 5 countries and battery data for 2; the rest are region-and-income peer means.

## 5. Solar resource

- PVGIS-ERA5, calendar year 2023 only, hourly. One call per facility lat/lon.
- 1 kWp DC nameplate, **0% system losses**, tilt = |latitude|, azimuth south.
- Annual yield ranges from about 950 kWh/kWp (northern Finland) to 1,950 kWh/kWp (southern Portugal).
- The solver ignores `inverter_efficiency` (`del inverter_efficiency`), so no inverter loss is applied.

## 6. Land availability

- ESA WorldCover v200 (2021), analyzed in GEE at 30 m, within a circular buffer around the Climate TRACE point (5 km baseline, 15 km sensitivity).
- Excluded pixels: slope > 5° (SRTM, Copernicus GLO-30 above 60°N) and WDPA protected areas plus a 100 m buffer.
- Available land = bare/sparse vegetation (class 60) + cropland (class 40) only. Built-up, tree cover, water and wetland are excluded.
- Packing density: 50 MWdc/km².
- Data vintage: land CSVs dated 2026-07-17.

## 7. Gas benchmark (comparison only, not in the optimization)

- `Input/industrial_heat_pump_costs/eu_heat_pump_costs_by_country.csv`: industrial gas price ÷ 0.85 boiler efficiency, plus EUA carbon at €79/tCO2, converted at EURUSD 1.08. GBR uses IRL.

## 8. Decisions made 2026-11-05 (code changed, baseline NOT yet rerun)

- Cost year: 2030 for all costs (README fixed).
- **PV system loss 14%** applied to the PVGIS hourly profiles in the model (`CONFIG["pv_system_loss"]`); PVGIS files are unchanged (still pulled at 0% loss).
- **GBR uses its own BNEF costs** (`CONFIG["gbr_proxy"] = None`). Gas benchmark still uses IRL for the GBR gas price only.
- **Battery VOM kept** (BNEF, per MWh discharged). PV VOM wired in, 0 in data.
- Heat-low and heat-high scenarios are not needed; dropped from the rerun plan.
- Spot check (site 38480285, FRA food): LCOH_served 34.46 → 38.25 (PV loss + VOM). A UK site: 51.44 → 46.48 (own CRF 0.0659 vs Ireland's 0.0896).
- Gas benchmark: per-country gas price (÷0.85 boiler efficiency) plus one EU-wide carbon adder of **€18.77/MWh_th** (= €79/tCO2 × 0.202 tCO2/MWh gas [IPCC 56.1 t/TJ] ÷ 0.85), identical in all 27 country rows and all sector rows. This reproduces exactly; an earlier note here said €17.33 and an 8% gap, which was my arithmetic error. There is no per-country carbon column: carbon is a single EUA price with no national carbon taxes, and GBR borrows IRL. Used for comparison at the aggregate availability figure and the gas-capped analyses only, not in the optimization. Gas prices are a current-price screening series with no stated year.

## 9. Open items before the numbers are firm

1. **DECIDE: cost year.** The baseline folders use 2030, but README lines 229 and 261 still describe 2025 as the base. Pick one and fix the README.
2. **DECIDE: PVGIS losses.** Solar yield uses 0% losses and no inverter loss, which overstates output by roughly 10–14% unless it is a deliberate idealization. This lowers LCOH. Decide whether to add a loss factor and rerun.
3. **DECIDE: GBR cost proxy.** 290 UK facilities are priced with Ireland (IRL) even though GBR has direct BNEF PV and battery data. IRL is itself imputed and has a higher CRF (0.0896 vs 0.0659).
4. **CHECK: CRF source and lifetime.** The CRF is IRENA-sourced. Confirm the lifetime embedded in it (the README says 25 years for solar) and that it is appropriate for HP, IHB and Li-ion.
5. **DONE in code 2026-11-05, baseline NOT yet rerun: battery VOM.** The solver now charges BNEF Li-ion VOM ($/MWh discharged, 2030: $5.4–16.6) in the objective and in the reported LCOH. Spot-check on 6 food sites: LCOH_served +$1.2–1.6/MWh. The by_facility.csv files in the liion folders still exclude VOM until rerun. PV VOM is also wired in ($/MWh generated, added to solar cost per MWdc) but is 0 in the BNEF file, so it changes nothing today (tested with a $10 stand-in: it works). HP and IHB have no VOM input in any cost file (IHB opex fraction is 0; HP VOM was removed earlier because it was 0), so they have none. CCGT, OCGT and coal VOM rows exist in the BNEF file but those technologies are not in the optimization.
5b. **CHECK/DECIDE: 2030 alignment.** Not at 2030 today: (a) gas benchmark prices (gas price, EUA €79, EURUSD 1.08, year unstated); (b) WACC/CRF, identical in the 2025 and 2030 rows; (c) heat inventory (Climate TRACE 2024, Eurostat 2024, Hotmaps 2014). Unverified: whether BNEF 2030 rows are nominal 2030 USD or real 2025 USD, which determines whether mixing them with CPI-inflated HP/IHB costs is consistent.
6. **CHECK: stale derived outputs.** Maps, compare_* files, heat-low/high figures and sector/country plots predate the COP change (see [[rissman-cop-rerun]]). Only by_facility.csv in the two liion folders is current.
7. **CHECK: input file dates.** The site assessment CSV (2026-10-08) is newer than the replaceable file (2026-07-24). Totals match at 522.3 TWh, but rerun `build_sites_input.py` if the heat inputs change.
8. **Known data caveats:**
   - Hotmaps production is 2014 vintage.
   - Climate TRACE food and textile emissions are modeled.
   - Iron and steel covers sinter and rolling only (about 54% of the Eurostat top-down).
   - Steam-cracking η = 0.90 is the least certain efficiency.
   - 16 representative days and a single solar year (2023) are the temporal simplifications.

## 10. BNEF Energy Storage Systems Cost Survey 2025 (checked 2026-11-05)

Files: `Input/Energy Storage Systems Cost Survey 2025 _ Full Report _ BloombergNEF.pdf` (45 pp, image-only, dated 2025-12-10) and `Input/2026-01-26 - Energy Storage Systems Cost Survey 2025.xlsx` (dataset sent 2025-12-12).

- **Dollar basis: real 2025 USD per usable kWh** (stated on every figure and sheet). Historical series CPI-adjusted to 2025.
- **Europe 4-hour "energy storage project cost"** (turnkey + EPC + developer overhead + developer margin; Raw Data sheet, real 2025 USD/kWh): **2025 = $252, 2030 = $192**. Europe 4 h turnkey only (Fig. 39): 2025 = $172, 2030 = $125. Non-China fully installed 4 h 2025 = $273 (turnkey $196 + EPC and grid connection $77).
- **Our Li-ion CAPEX (`bnef_country_costs.csv`, 4 h, per kWh = $/kW ÷ 4):** 2025: ESP/FRA/ITA/POL/IRL $252.7, DEU $260.1, GBR $245.3. 2030: proxied countries $181.8, DEU $187.2, GBR $176.5. The 2025 proxied value ($252.7) is the mean of the DEU and GBR rows (see section 11) and happens to match the survey's Europe project cost ($252); 2030 is about 5% below the survey's $192. The country rows come from a different BNEF dataset than this survey (section 11).
- **The survey contains no FOM or VOM.** The Excel states O&M, LTSA and decommissioning are not included. Closest O&M indicator: LTSA costs of 0.5–6% of capex, or $2–4/kWh-yr (median LTSA tenor 17.5 yr; 84% of projects have one; scope = capacity maintenance, availability and round-trip-efficiency guarantees). At $2–4/kWh-yr, 4 h = $8–16/kW-yr, versus our 2030 FOM of $6.9–7.3/kW-yr. At one full 4 h cycle per day, our VOM ($5.4–12.2/MWh) adds about $8–18/kW-yr, so FOM + VOM ≈ $15–25/kW-yr, above the LTSA range. Possible overlap between VOM and LTSA/FOM scope; origin of the FOM/VOM columns unverified.
- **Performance benchmarks (medians):** AC-AC round-trip efficiency 87.5% (range 85–98%); model uses 90%. Annual degradation 1.77%; end-of-life state of health 65%; project redundancy 10%; warranty 15 yr; cycle life 8,000 cycles. The model has no degradation or replacement cost.
- **Dollar-basis consequence:** if BNEF PV/Li-ion are real 2025 USD, then (a) CPI-inflating heat pump and IHB to 2030 nominal USD mixes bases, and (b) `wacc_nominal`-based CRFs are applied to real-dollar costs. Both need a consistent choice.

## 11. Provenance of `Input/bnef_country_costs.csv` (found 2026-11-05 in ~/Downloads/industrial_facilities_db.zip)

- `Input/bnef_country_costs.csv` is **byte-identical** to `BNEF/output/bnef_country_costs.csv` in the zip, built by `BNEF/scripts/compile_bnef_costs.py` (author Anna Yuen, 2026-02-04, VERSION v5). Zip extracted selectively to the session scratchpad; nothing was run.
- **Source dataset:** `BNEF/input/BNEF_raw_data_2024.xlsx` (Sheet1, 2,320 rows, years 2014–2050, scenarios Low/Mid/High; the script uses **Mid**). Metrics: Capex ($/kW), Fixed O&M ($/MW/yr), Variable O&M ($/MWh), LCOE ($/MWh), Short-run marginal cost. Technologies include PV fixed-axis, PV tracking, Utility-scale battery (1h, 4h), CCGT, OCGT, Coal. **It carries no dollar-year note.** It is a different BNEF dataset from the Energy Storage Systems Cost Survey.
- **Battery (4h) has only 8 countries of direct data:** Australia, Chile, China, Germany, India, Japan, UK, US. Europe fleet countries other than DEU and GBR get the region+income peer mean, which for Europe is the mean of DEU and GBR. FOM and VOM are BNEF's own values from the same dataset.
- **CRF construction:** `LIFETIME = 25` years for every technology. WACC = IRENA cost-of-capital for **Solar PV** (a **real** WACC, `IRENA_cost_of_cap.json`) inflated to nominal with the IMF WEO April 2025 CPI forecast averaged over 2025–2030 (`weoapr2025all.csv`); fallback inflation 3%. The same Solar PV CRF is reused for battery, coal, CCGT, OCGT (and, in our model, for HP and IHB). The CRF is identical in the 2025 and 2030 rows because it is not year-specific.
- **Consistency issue:** the nominal WACC is applied to BNEF capex whose dollar basis is not documented in the raw file. If the capex is real, the consistent discount rate is the IRENA real WACC before inflation.
- **Newer data in the zip, not used by the compile script:** `raw_data/2025-12-04 - LCOE Data.xlsb` (BNEF LCOE data, December 2025 vintage; the compiled file used the 2024 raw data). Also in the zip: the Energy Storage Systems Cost Survey xlsx (same file as in Input), Global Oil and Gas Plant Tracker and Global Coal Plant Tracker (Jan 2026), European wholesale electricity prices.
- Unused side outputs: `battery_2025_cost.csv` (battery component table inflated to 2025 USD with US inflation), `bnef_solar_pv_costs_v4.csv`, `bnef_RE_mid*.csv`.
- **Copied into the repo 2026-11-05:** `Input/bnef/` now holds the compile script, `input/` data files and a README. Script paths were changed to be relative to its own folder; logic is unchanged. Running it reproduces `Input/bnef_country_costs.csv` (all 1,964 rows and 17 columns match to 1e-9). Generated output was deleted after the check.
