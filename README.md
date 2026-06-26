# Industrial Heat Battery Potential at Pulp and Paper Facilities

## Overview

This research assesses the global potential for Industrial Heat Batteries (IHBs) to displace fossil-fueled heat at pulp and paper facilities. Using facility-level production estimates from Climate TRACE, we estimate replaceable thermal demand, then compare the levelized cost of heat (LCOH) from two supply options:

1. **Colocated renewable path** — solar generation plus IHB storage
2. **Fossil baseline** — natural gas combined-cycle gas turbine (CCGT) heat

Sites where the renewable path is cost-competitive (or otherwise favorable) are flagged as potential IHB candidates. The analysis also quantifies the emissions and cost benefits of deployment at those sites.

## Research Questions

- How much fossil-replaceable heat demand exists across global pulp and paper facilities?
- Which facilities have favorable economics for colocated solar + IHB vs. CCGT heat?
- What site-level conditions (solar resource, land availability, heat profile, country-level costs) drive competitiveness?
- What are the aggregate decarbonization and cost implications of targeting high-potential sites?

## Scope and Assumptions

- **Sector:** Pulp and paper industrial facilities globally.
- **Heat replacement boundary:** Only the fossil share of facility heat demand is considered replaceable by IHB (see fossil share table below).
- **Supply options compared:** Colocated solar + IHB vs. CCGT-generated heat.
- **Cost data:** Country-level LCOE/LCOH inputs from Bloomberg (solar, battery, CCGT).
- **Solar siting:** Available land is limited to bare land, cropland, and building footprints within the facility area (Google Earth Engine).
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
| Heat load shape | Sample heat profiles | Daily/seasonal heat demand profiles |
| Validation benchmarks | Facility disclosures (e.g., ENCE annual reports) | Sanity-check production estimates |

## Methodology

### 1. Replaceable Heat Demand

Annual heat demand and the IHB-replaceable portion are estimated per facility using Climate TRACE production data, a capacity factor, and sector-specific intensity and fossil-share assumptions.

Each facility is categorized by primary output: **Pulp**, **Integrated pulp+paper**, **Paper/board**, or **Tissue**. Category determines the heat intensity applied.

| Product category         | Thermal SEC (MWhth/t) | Equivalent (GJ/t) | Source                                                                              |
| ------------------------ | --------------------: | ----------------: |----------------------------------------------------------------------------------- |
| Virgin pulp (kraft pulp) |               ~4 |             ~12 | [Energy Cost Reduction in the Pulp and Paper Industry](https://ressources-naturelles.canada.ca/sites/www.nrcan.gc.ca/files/oee/pdf/publications/infosource/pub/cipec/pulp-paper-industry/pdf/pulp-paper-industry.pdf) |
| Integrated pulp + paper  |               4.0–6.0 |             14-20 | [BAT Reference Document for Pulp, Paper and Board Industry](https://bureau-industrial-transformation.jrc.ec.europa.eu/sites/default/files/2020-03/superseded_ppm_bref-1201.pdf)                           |
| Paper & board            |               1.1-1.6 |              4-6 | [BAT Reference Document for Pulp, Paper and Board Industry](https://bureau-industrial-transformation.jrc.ec.europa.eu/sites/default/files/2020-03/superseded_ppm_bref-1201.pdf)                             |
| Tissue                   |               2.0–3.3 |              7–12 | [BAT Reference Document for Pulp, Paper and Board Industry](https://bureau-industrial-transformation.jrc.ec.europa.eu/sites/default/files/2020-03/superseded_ppm_bref-1201.pdf)         |

Heat Intensity Values Chosen: 

| Category | Heat intensity |
|----------|----------------|
| Pulp | 4.0 MWh<sub>th</sub>/t |
| Integrated pulp+paper | 5.0 MWh<sub>th</sub>/t |
| Paper/board | 1.3 MWh<sub>th</sub>/t |
| Tissue | 2.6 MWh<sub>th</sub>/t |


Fossil Share is calculated using [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nrg_d_indq_n/default/table?lang=en) natural gas, coal, oil & Petroleum against totals.

$$
\text{Fossil Share}_{c} = \frac{E_{\text{natural gas},c} + E_{\text{coal},c} + E_{\text{oil},c} + E_{\text{mfg gases},c}}{E_{\text{total},c}}
$$


$$
\text{Heat}_i = \text{Production}_i \times \text{Intensity}_{product}
$$

$$
\text{Replaceable Heat}_i = \text{Heat}_i \times \text{Fossil Share}_{country}
$$

Where:
- **Production**<sub>i</sub> = annual output (t/yr), from Climate TRACE capacity × capacity factor
- **Intensity**<sub>i</sub> = sector-specific thermal energy per ton of output
- **Fossil Share**<sub>i</sub> = fraction of heat currently met by fossil fuels

> **TODO:** Document capacity factor source and facility categorization rules (how output type is assigned when a site produces multiple products).

### 2. Validation

Production estimates are checked against reported facility output where public data is available.

**Example — ENCE pulp mills (Spain):**

| Site | Reported (2020) | Estimated (2021) | Method |
|------|-----------------|------------------|--------|
| ENCE Navia | 572,567 t pulp/yr | 564,274 t pulp/yr | 685,000 × 0.824 capacity factor |
| ENCE Pontevedra | 434,718 t pulp/yr | 424,235 t pulp/yr | 515,000 × 0.824 capacity factor |

Reported values from [ENCE pulp business disclosures](https://ence.es/en/pulp-business/). Estimates are within ~2% of reported production, supporting use of Climate TRACE capacity × capacity factor for annual output.

> **TODO:** Add additional validation sites and note any systematic biases (year mismatch, product mix, etc.).

### 3. Heat Profile

Sample heat profiles are used to approximate the shape of daily (and potentially seasonal) heat demand at representative facilities. These profiles scale total replaceable heat to an hourly or sub-daily load curve for sizing solar and IHB capacity.

> **TODO:** Specify profile source(s), whether profiles differ by facility category, and how peak/average heat load is derived.

### 4. Solar Resource

For each facility, latitude and longitude are used to retrieve 2023 solar radiation from PVGIS. This supports estimation of colocated solar generation potential.

> **TODO:** Note PVGIS dataset/parameters used (e.g., hourly GHI/DNI, tilt/azimuth assumptions, system losses).

### 5. Land Availability

Using Google Earth Engine, land within each facility footprint is classified and summed across categories treated as suitable for solar development:

- Bare land
- Cropland
- Building footprints

The total available area constrains the maximum colocated solar array size per site.

> **TODO:** Define spatial boundary (buffer around facility point vs. parcel polygon), resolution, and any exclusion rules.

### 6. Technology Costs

Country-level cost inputs are taken from Bloomberg for:

- Solar PV LCOE
- Battery storage LCOE (IHB)
- CCGT LCOE / fuel cost for heat generation

Each facility uses the cost values for its country of operation.

> **TODO:** Specify Bloomberg dataset vintage, currency, and whether costs are converted or escalated.

### 7. LCOH Calculations

LCOH is computed for each facility under both supply paths, using replaceable heat demand, heat profile, solar resource, available land, and country-level costs.

**Renewable path (solar + IHB):**

> **TODO:** Add equation(s) for solar array sizing, battery sizing, and LCOH<sub>solar+IHB</sub>.

**Fossil baseline (CCGT):**

> **TODO:** Add equation(s) for LCOH<sub>CCGT</sub>.

**Comparison:**

> **TODO:** Define decision criteria — e.g., LCOH<sub>solar+IHB</sub> < LCOH<sub>CCGT</sub>, minimum land area, minimum solar yield, etc.

### 8. Site Screening and Results

Facilities meeting the screening criteria are classified as potential IHB candidates. Summary outputs may include:

- Total replaceable heat demand (global and by region/country)
- Number and share of sites that are economically favorable
- Distribution of LCOH deltas (renewable vs. CCGT)
- Aggregate emissions reduction potential

> **TODO:** Define output tables/maps and summary metrics to publish.

### 9. Sensitivity Analysis

Test how robust site rankings and aggregate results are to uncertainty in key inputs. Vary one parameter at a time (or in defined combinations) and compare changes in LCOH, candidate site count, and total replaceable heat.

> **TODO:** Define sensitivity scenarios and ranges, for example:
> - **Fossil share** — ±10–20% around sector-average values
> - **Heat intensity** — ±10–20% by facility category
> - **Technology costs** — solar PV, battery/IHB, and CCGT LCOE (e.g., ±20% or low/base/high country cases)
> - **IHB round-trip efficiency** — impact on storage sizing and LCOH
> - **Solar resource** — PVGIS year or inter-annual variability
> - **Available land** — stricter vs. more permissive land classifications
> - **Capacity factor** — production estimate uncertainty
>
> **TODO:** Specify output format — tornado charts, site count vs. parameter curves, or maps showing how candidate sites change under each scenario.

## Limitations

> **TODO:** Capture known limitations — e.g., reliance on sector-average intensity/fossil share, simplified land screening, country-level rather than site-level costs, heat profile representativeness, Climate TRACE data uncertainty.

## References

> **TODO:** Add full citations for Climate TRACE, PVGIS, Bloomberg, heat intensity/fossil share assumptions, and validation sources.
