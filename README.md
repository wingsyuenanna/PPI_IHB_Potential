# Industrial Heat Battery Potential at Pulp and Paper Facilities

## Overview

This research assesses the EU potential for Industrial Heat Batteries (IHBs) to displace fossil-fueled heat at pulp and paper facilities. Using facility-level production estimates from Climate TRACE, we estimate replaceable thermal demand, then compare the levelized cost of heat (LCOH) from two supply options:

1. **Colocated renewable path** — solar generation plus IHB storage
2. **Fossil baseline** — natural gas boiler heat

Sites where the renewable path is cost-competitive (or otherwise favorable) are flagged as potential IHB candidates. The analysis also quantifies the emissions and cost benefits of deployment at those sites.

## Research Questions

- How much fossil-replaceable heat demand exists across EU pulp and paper facilities?
- Which facilities have favorable economics for colocated solar + IHB vs. CCGT heat?
- What site-level conditions (solar resource, land availability, heat profile, country-level costs) drive competitiveness?
- What are the aggregate decarbonization and cost implications of targeting high-potential sites?

## Scope and Assumptions

- **Sector:** Pulp and paper industrial facilities.
- **Heat replacement boundary:** Only the fossil share of facility heat demand is considered replaceable by IHB (see fossil share table below).
- **Steam scope:** Replaceable heat is modeled as process steam (kraft digesters \~170 °C, paper drying \~180 °C), which a steam-delivering IHB can serve. Lime-kiln fuel at kraft mills (\~900 °C direct firing, roughly 8–12% of mill fuel input) is outside this scope: an IHB does not fire a rotary kiln, and the kiln is not modeled separately. Where country-average fossil shares include kiln fuel, addressable demand at fossil-fired kraft (Pulp/Integrated) sites is somewhat overstated; at many Nordic mills the kiln already burns biomass and is excluded via the fossil share.
- **Supply options compared:** Colocated solar + IHB vs. CCGT-generated heat.
- **Cost data:** Country-level LCOE/LCOH inputs from Bloomberg (solar, battery, CCGT).
- **Solar siting:** Available land is limited to bare land and cropland within ~5 km of each facility (Google Earth Engine). Built-up areas are excluded.
- **Solar resource:** Hourly/daily solar radiation from PVGIS (2023), based on facility latitude and longitude.

> **TODO:** Document key assumptions not yet captured — discount rate, project lifetime, IHB round-trip efficiency, capacity factor sources, and how facility output type (pulp vs. tissue, etc.) is assigned.

## Data Sources

| Data | Source | Use |
|------|--------|-----|
| Facility production capacity | Climate TRACE | Annual production estimates per site |
| Solar radiation | PVGIS (2023) | Site-specific solar resource |
| Land cover / available area | Google Earth Engine | Estimates of land suitable for colocated solar |
| Technology costs (solar, battery, CCGT) | Bloomberg (by country) | LCOH inputs per facility |
| Heat intensity & fossil share | Sector-specific assumptions (table below) | Replaceable heat calculations |
| Heat load shape | Flat hourly profile (derived) | Constant load from annual replaceable heat |
| Validation benchmarks | Facility disclosures (e.g., ENCE annual reports) | Sanity-check production estimates |

## Methodology

We apply a bottom-up production-activity approach, estimating heat demand as output × specific heat intensity × fossil share. Heat intensities are drawn from [BREFs / the same engineering sources underlying JRC-IDEES]. The fossil share is taken from Eurostat sector-level data. This inverts the more common European top-down approach (e.g. JRC-IDEES, Fraunhofer ISI 2016), which anchors to Eurostat energy balances and uses production as a disaggregation weight; we instead use facility-level production directly.

### 1. Replaceable Heat Demand

Annual heat demand and the IHB-replaceable portion are estimated per facility using Climate TRACE production data, a capacity factor, and sector-specific intensity and fossil-share assumptions.

Each facility is categorized by primary output: **Pulp**, **Integrated pulp+paper**, **Paper/board**, or **Tissue**. Category determines the heat intensity applied.

| Product category         | Thermal SEC (MWhth/t) | Equivalent (GJ/t) | Source                                                                              |
| ------------------------ | --------------------: | ----------------: |----------------------------------------------------------------------------------- |
| Virgin pulp (kraft pulp) |               ~3.3 |             ~12 | [Energy Cost Reduction in the Pulp and Paper Industry](https://ressources-naturelles.canada.ca/sites/www.nrcan.gc.ca/files/oee/pdf/publications/infosource/pub/cipec/pulp-paper-industry/pdf/pulp-paper-industry.pdf) |
| Integrated pulp + paper  |               4.0–6.0 |             14-20 | [BAT Reference Document for Pulp, Paper and Board Industry](https://bureau-industrial-transformation.jrc.ec.europa.eu/sites/default/files/2020-03/superseded_ppm_bref-1201.pdf)                           |
| Paper & board            |               1.1-1.6 |              4-6 | [BAT Reference Document for Pulp, Paper and Board Industry](https://bureau-industrial-transformation.jrc.ec.europa.eu/sites/default/files/2020-03/superseded_ppm_bref-1201.pdf)                             |
| Tissue                   |               2.0–3.3 |              7–12 | [BAT Reference Document for Pulp, Paper and Board Industry](https://bureau-industrial-transformation.jrc.ec.europa.eu/sites/default/files/2020-03/superseded_ppm_bref-1201.pdf)         |

Heat Intensity Values Chosen: 

| Category | Heat intensity |
|----------|----------------|
| Pulp | 3.3 MWh<sub>th</sub>/t |
| Integrated pulp+paper | 5.0 MWh<sub>th</sub>/t |
| Paper/board | 1.3 MWh<sub>th</sub>/t |
| Tissue | 2.6 MWh<sub>th</sub>/t |


Fossil Share is calculated using [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nrg_d_indq_n/default/table?lang=en) natural gas, coal, oil & Petroleum against totals.

```
Fossil Share_c = (E_natural gas,c + E_coal,c + E_oil,c + E_mfg gases,c) / E_total,c

Heat_i = Production_i × Intensity_product

Replaceable Heat_i = Heat_i × Fossil Share_country
```

Where:
- **Production**_i = annual output (t/yr), from Climate TRACE capacity × capacity factor
- **Intensity**_i = sector-specific thermal energy per ton of output
- **Fossil Share**_i = fraction of heat currently met by fossil fuels

> **TODO:** Document capacity factor source and facility categorization rules (how output type is assigned when a site produces multiple products).

### 2. Validation
To validate the bottom-up approach, facility-level heat demand was aggregated to country level and compared against Eurostat C17 combustion-energy totals. In countries with high facility coverage (France 59%, Portugal 51%), the bottom-up estimate recovers a plausible majority of sector combustion energy without exceeding it. Lower coverage ratios elsewhere (Germany 10%, Sweden 26%) reflect incomplete facility matching in Climate TRACE rather than methodological bias, consistent with the proxy-capacity limitations documented in the dataset. Production estimates are checked against reported facility output where public data is available.

**Example — ENCE pulp mills (Spain):**

| Site | Reported (2020) | Estimated (2021) | Method |
|------|-----------------|------------------|--------|
| ENCE Navia | 572,567 t pulp/yr | 564,274 t pulp/yr | 685,000 × 0.824 capacity factor |
| ENCE Pontevedra | 434,718 t pulp/yr | 424,235 t pulp/yr | 515,000 × 0.824 capacity factor |

Reported values from [ENCE pulp business disclosures](https://ence.es/en/pulp-business/). Estimates are within ~2% of reported production, supporting use of Climate TRACE capacity × capacity factor for annual output.

> **TODO:** Add additional validation sites and note any systematic biases (year mismatch, product mix, etc.).

### 3. Heat Profile

Heat demand is estimated at **annual** resolution only (production × SEC × fossil share). No hourly or seasonal mill data are available at facility level from Climate TRACE or the workbook, so temporal shape cannot be inferred site-by-site from production statistics alone.

**Assumption:** replaceable heat is modeled as a **flat (constant) hourly load** over the year:

```
Hourly heat load (kW_th) = Replaceable Heat_i (MWh_th/yr) × 1,000 / 8,760
```

This flat profile is used when aligning heat demand with hourly PVGIS solar output for sizing colocated solar and IHB capacity. It implies:

- No diurnal ramping (e.g. higher steam demand during day shifts)
- No seasonal variation (e.g. higher demand in winter)
- Average load equals peak load for sizing purposes

Real pulp and paper mills typically show within-day and seasonal variation. The flat load is therefore a **deliberate simplification** driven by the annual aggregation step; it tends to understate peak requirements and may over- or under-state storage needs depending on how heat load and solar generation correlate in practice. More detailed load shapes can be substituted in sensitivity analysis where representative profiles are available.

### 4. Solar Resource

For each facility, latitude and longitude are used to retrieve hourly PV output from the [PVGIS API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en) (`seriescalc` endpoint). This supports estimation of colocated solar generation potential and hourly alignment with heat load profiles.

**Script:** `solar_radiation/pull_pvgis.py`  
**Inputs:** `heat_demand/facilities/facilities_2024_eu.csv` (one row per facility, `source_id` + lat/lon)  
**Outputs:**
- `solar_radiation/outputs/solar_radiation_by_facility.csv` — annual summary per site
- `solar_radiation/outputs/hourly_profiles/{source_id}_2023.parquet` — 8,760 hourly rows per site (`P_kWperkWp`)

```bash
python3 solar_radiation/pull_pvgis.py
```

Re-run with `--overwrite` to refresh all profiles; already-downloaded sites are skipped by default.

#### PVGIS parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Radiation database | **PVGIS-ERA5** | Reanalysis-based irradiance |
| Year | **2023** | Single calendar year |
| System size | **1 kWp** | Output normalized per kWp installed |
| System losses | **0%** | Idealized resource; apply losses in LCOH/sizing step |
| Tilt | **\|latitude\|** | Steep latitude-tilt rule from prior workflow; not necessarily optimal fixed tilt |
| Azimuth | **0°** (south) in Northern Hemisphere; **180°** in Southern Hemisphere | |
| Output variable | **P** (W) → `P_kWperkWp` | Hourly AC power per kWp, kW/kWp |

Timestamps from PVGIS (UTC) are converted to the local timezone at each coordinate (via `timezonefinder`), rounded to the nearest hour, deduplicated, and reindexed to a complete local hourly series for the target year (missing hours filled with 0).

#### Summary metrics

- **`annual_yield_kwh_per_kwp`** — sum of hourly `P_kWperkWp` (= kWh per kWp per year)
- **`solar_capacity_factor`** — `annual_yield_kwh_per_kwp / 8760`

For the current EU facility set (2023), annual yield ranges from ~950 kWh/kWp (northern Finland) to ~1,950 kWh/kWp (southern Portugal), consistent with latitude and the tilt/loss assumptions above.

> **Note:** Results are comparable across sites under identical PVGIS settings. For absolute generation or LCOH, consider adding a standard system-loss factor (e.g. 10–14%) and/or a fixed tilt sensitivity case.

### 5. Land Availability

Land suitable for colocated solar is estimated in Google Earth Engine (GEE) as the area of selected land-cover classes within a buffer around each facility point. The default **5 km** buffer reflects on-site or immediately adjacent siting for colocated arrays; a **15 km** buffer is reserved for sensitivity analysis only.

**Scripts:** `land_availability/prepare_gee_upload.py` → `land_availability/gee_facility_calculate_available_area.py` → `land_availability/merge_land_availability.py`  
**Exploratory notebook:** `land_availability/GEE_facility_calculate_available_area.ipynb` (maps and buffer tests only; use the Python script for production exports)

#### Spatial boundary and resolution

| Setting | Default | Description |
|---------|---------|-------------|
| Facility geometry | **Point** (Climate TRACE lat/lon) | No parcel polygons |
| Buffer | **5,000 m** radius | Circular buffer around each point |
| Land cover | **ESA WorldCover v200 (2021)** | 10 m product aggregated at 30 m for zonal stats |
| Analysis scale | **30 m** | `reduceRegion` scale in GEE |
| GEE project | **`eu-re-potential`** | Earth Engine Cloud project |

#### Suitability mask (environmental exclusions)

Before summing land-cover classes, pixels are masked out if they fail either test:

1. **Slope** — terrain slope **> 5°** (excluded). Elevation from **SRTM** (30 m) where available; **Copernicus DEM GLO-30** fills gaps **above 60°N** (Finland, northern Sweden), where SRTM has no coverage.
2. **Protected areas** — pixels within **WDPA** polygons (status: Designated, Inscribed, or Established), with a **100 m** buffer around protected boundaries.

Remaining pixels are grouped by WorldCover class and summed to km² within the facility buffer.

#### Land-cover classes and available area

All WorldCover classes are exported for transparency. **Available land for colocated solar** counts only:

- **Bare / sparse vegetation** (`bare_sparse_km2`, WorldCover class 60)
- **Cropland** (`cropland_km2`, class 40)

**Excluded from available land:** built-up (50), tree cover (10), water (80), wetland (90), and other classes — roofs, roads, forest, and water bodies are not treated as array siting area.

```
available_land_km² = bare_sparse_km² + cropland_km²
```

#### Pipeline

```bash
# 1. Export facility points (after facilities CSV is current)
python3 land_availability/prepare_gee_upload.py

# 2. Upload Input/facilities_2024_eu_gee_upload.csv in GEE Console as a table asset

# 3. Start batch export to Google Drive (requires `earthengine authenticate`)
python3 land_availability/gee_facility_calculate_available_area.py \
  --project eu-re-potential \
  --asset projects/eu-re-potential/assets/facilities_2024_eu_gee_upload \
  --buffer-m 5000

# 4. Download Drive CSV → Input/LandCover_Area_Categorized_5km.csv

# 5. Merge with facility metadata
python3 land_availability/merge_land_availability.py \
  --land-export Input/LandCover_Area_Categorized_5km.csv
```

**Output:** `land_availability/outputs/land_availability_by_facility.csv` — facility metadata plus all land-cover km² columns and `available_land_km2`.

#### Limitations

- Point + buffer is a screening metric, not a land-ownership or permitting assessment.
- Cropland may be technically suitable by land cover but restricted by agricultural use or policy.
- WorldCover and WDPA vintages (2021 / current WDPA) may not reflect recent land-use change.
- Zonal sums are approximate at 30 m scale; very small available areas near the resolution limit should be interpreted cautiously.

### 6. Technology Costs

Technology costs are country-level and expressed in **nominal 2025 USD**. CAPEX, fixed O&M, WACC, and CRF for fixed-axis solar PV, utility-scale batteries, and CCGT come from BloombergNEF tables compiled in `Input/bnef_country_costs.csv` (cost year **2025**; 2030 retained for sensitivity). Missing countries are proxied by income/region peers; UK facilities use Ireland as the price proxy. Solar CAPEX is annualized with the country CRF implied by BNEF WACC and a **25-year** lifetime.

**IHB / thermal storage** (from `flatblock_optimization/inputs/input_heat_battery_cost.csv`, 2025 base):

| Parameter | Value |
|-----------|-------|
| Thermal energy CAPEX | $100/kWh_th |
| Fixed O&M | 2% of CAPEX / yr |
| Lifetime | 25 years |
| Discount rate (storage CRF) | 7% |
| Round-trip efficiency | 92% |
| Electric→heat efficiency | 98% (≤200 °C) / 95% (>200 °C) |
| Inverter efficiency | 96.7% |
| Max storage duration | 16 h |
| Min charge:discharge power | 4:1 |
| PV land intensity | 50 MWdc/km² |

Heat delivery COP: 2.7 (&lt;100 °C HP), 1.8 (100–200 °C steam HP), 1.0 (&gt;200 °C resistive/IHB). Primary multi-band runs exclude converter equipment CAPEX from LCOH (solar + storage only). Country CCGT LCOE is the fossil heat benchmark (~$130–140/MWh in EU 2025).

### 7. LCOH Calculations

Per facility, a HiGHS LP sizes shared solar + per-band thermal storage over 16 representative PVGIS days (flat band loads; COP 2.7 / 1.8 / 1.0; 90% availability floor; land cap at 50 MWdc/km²). Primary LCOH excludes converter CAPEX and VoLL:

\[
\mathrm{LCOH}_{served} = C_{ann} / Q_{served},\quad
\mathrm{LCOH}_{total} = C_{ann} / Q_{demand}
\]

with \(C_{ann}\) = annualized solar (country CRF) + annualized thermal storage (7%, 25 yr, 2% O&M). Fossil screen: compare \(\mathrm{LCOH}_{served}\) to country BNEF CCGT LCOE (~$130–140/MWh EU 2025).

### 8. Site Screening and Results

Runnable fleet: 2,192 sites. Base (2025, solar+storage, 5 km): 1,925 sites meet 90% (39% of heat); HW reliability 59%; HW LCOH_served ~$82/MWh (median ≥90% ~$71). At 15 km: 2,148 sites (75% of heat); HW reliability 86%; HW LCOH ~$110/MWh (median ≥90% ~$74). Outputs: `outputs/multiband/<scenario>/by_facility.csv`, summary tables, dual LCOH maps.

### 9. Sensitivity Analysis

- **Land:** 5 km vs 15 km buffers.
- **Heat demand:** sector low/base/high multipliers (fleet 388 / 522 / 697 TWh/y) via `--heat-case`.
- Higher heat → fewer ≥90% sites / lower heat share; fleet HW LCOH can fall via composition (within-site median ΔLCOH ≈ 0).
- Extensions: 2030 costs, converter CAPEX on/off, storage CAPEX path, RTE, stricter land masks.

## Limitations

Sector-average SEC / fossil shares / Hotmaps band recipes; flat load; point-buffer land (not permitting); country BNEF + stylized IHB costs; converter CAPEX often excluded in primary LCOH; representative days suited to ≤16 h storage; CCGT LCOE is a coarse heat benchmark; Climate TRACE coverage is a screening-level floor.

## Archive

Superseded single-band runners, solvers, docs, and ~100 MB of hourly dumps live under [`archive/`](archive/) (`legacy_singleband/`, `flatblock_singleband_outputs_2025_2030.tar.gz`). Active entrypoint: `run_multiband_potential.py`.

## References

> **TODO:** Add full citations for Climate TRACE, PVGIS, Bloomberg, heat intensity/fossil share assumptions, and validation sources.
