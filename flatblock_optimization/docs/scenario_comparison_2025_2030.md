# Scenario comparison: 2025 vs 2030 costs

Solar + industrial heat battery (TES) serving fossil **steam** demand at EU pulp & paper
sites — flat load, 90% availability target, 12 h max storage duration, solar year 2023.
Generated 2026-07-06 by `run_ihb_potential.py`; per-scenario outputs in
`flatblock_optimization/output/` (2025) and `flatblock_optimization/output_2030/` (2030).
Demand basis (updated 2026-07-06 to match README): virgin pulp SEC **3.3 MWh_th/t** (NRCan,
was 4.0), Tissue **2.6** (BREF midpoint, was 1.5), Integrated 5.0, Paper/Board 1.3
(`pulp_paper_heat_demand_corrected.xlsx`).

**What changes between scenarios:** the cost year only. TES CAPEX falls from
**$100/kWh (2025) to $20/kWh (2030)** (`input_heat_battery_cost.csv`), and solar
CAPEX/FOM/CRF move to BNEF 2030 country values. Demand, solar profiles, land, and all
other assumptions are identical. Both runs use the corrected TES discount rate (7%/yr;
see notebook correction note of 2026-07-05).

**Fossil steam benchmark:** gas-boiler LCOH ≈ €43–100/MWh_th (~$45–110), central
~$72/MWh — Agora Industry / Fraunhofer ISI (2025), *The business case for electrifying*
*industrial heat* (`References/`). Parity below is assessed against $72 (medium) and $110 (high).

## Headline statistics

| Metric | 2025 costs | 2030 costs |
|---|---|---|
| Sites completed | 60 / 65 | 60 / 65 |
| Steam heat covered (TWh_th/yr) | 14.6 | 14.6 |
| LCOH median ($/MWh_th) | 124 | 73 |
| LCOH p25–p75 | 84 – 252 | 50 – 175 |
| LCOH min – max | 48 – 709 | 27 – 402 |
| LCOH solar component, median | 80 | 61 |
| LCOH TES component, median | 40 | 12 |
| TES share of LCOH, median | 33% | 17% |
| Sites ≤ $72 (fossil medium) | 12 | 29 |
| Sites ≤ $110 (fossil high) | 22 | 41 |
| Sites whose optimal solar fits land | 35 | 39 |
| Steam heat at land-fitting sites | 27% | 34% |
| **Viable sites (fit land AND ≤ $110)** | **16** | **35** |
| **Steam heat at viable sites** | **12%** | **33%** |
| Solar overbuild (S/load), median | 16.5× | 14.3× |
| TES energy (MWh), median | 377 | 598 |
| TES duration at discharge, median | 12.0 h | 12.0 h |

## Median LCOH by country ($/MWh_th)

| Country | Sites | 2025 | 2030 | Δ |
|---|---|---|---|---|
| PRT | 6 | 56 | 34 | −40% |
| FRA | 5 | 68 | 39 | −43% |
| ESP | 3 | 70 | 40 | −42% |
| BGR | 1 | 79 | 44 | −44% |
| HRV | 2 | 84 | 51 | −39% |
| SVN | 1 | 84 | 50 | −40% |
| HUN | 1 | 87 | 50 | −43% |
| AUT | 2 | 92 | 55 | −40% |
| SVK | 2 | 116 | 69 | −40% |
| CZE | 2 | 118 | 71 | −39% |
| BEL | 1 | 125 | 75 | −40% |
| DEU | 10 | 125 | 74 | −41% |
| POL | 3 | 159 | 100 | −37% |
| SWE | 10 | 221 | 136 | −39% |
| FIN | 11 | 439 | 282 | −36% |

## Median LCOH by classification ($/MWh_th)

| Classification | Sites | 2025 | 2030 |
|---|---|---|---|
| Pulp | 20 | 119 | 71 |
| Paper/Board | 18 | 124 | 73 |
| Integrated | 19 | 133 | 79 |
| Tissue | 3 | 451 | 282 |

## Maps and notebooks

- 2025 map: `flatblock_optimization/output/map_sites_lcoh.html`
- 2030 map: `flatblock_optimization/output_2030/map_sites_lcoh_2030.html`
- Analysis notebook (2025, with loopholes L1–L11): `notebooks/ihb_steam_scope_results_analysis.ipynb`

## Caveats (abridged; full list in the notebook)

- Land is a post-hoc flag, not an LP constraint — "viable" above means the *unconstrained*
  optimum fits; land-constrained designs at other sites are not evaluated.
- Reliability is pinned at 90% by construction (VoLL = 0); remaining 10% of heat stays on
  the existing boiler, whose cost is not included.
- Flat load profile, single solar year (2023), lime-kiln fuel excluded by scope statement.
- 2030 solar/TES costs are projections (BNEF; DOE-style TES learning curve).
