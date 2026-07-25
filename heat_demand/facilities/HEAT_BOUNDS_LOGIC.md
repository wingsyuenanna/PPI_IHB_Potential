# Heat low/base/high bounds — table form

Multipliers in `heat_sensitivity_bounds.py` scale base `replaceable_heat_mwh_th`.
Band shares fixed. Fleet on runnable sites: **388 / 522 / 697 TWh/y**.

| Sector | Base calculation | Low × | High × | Logic |
|---|---|---:|---:|---|
| **Cement** | production × **2.8 GJ/t** × **η 0.60** × fossil share (SEC ≈ 3.5 GJ/t clinker × 0.77 clinker/cement; η = Madlool kiln first-law, top of 50–60%) | **0.85** | **1.60** | Low: η = 0.50 instead of 0.60 → 0.50/0.60 ≈ 0.85 (same SEC). High: METHODS ≈ 65 TWh vs Hotmaps/benchmark ≈ 104 TWh → ratio **1.60**. |
| **Lime** | production × **4.5 GJ/t** × **η 0.65** × fossil share (EU average SEC; η = shaft ~0.80 / rotary ~0.55 mix) | **0.80** | **1.50** | Span published SEC 3.6–7.5 GJ/t (EuLA/BREF) and kiln-type η (≈ −20% to +50% around base). |
| **Glass** | production × **6.5 GJ/t** × **η 0.45** × fossil share (EU melting + working; furnace η mid of 40–50%) | **0.85** | **2.00** | Low: η toward high-efficiency end of 40–50%. High: METHODS vs Hotmaps ratio ≈ 2.7; capped at **2.0**. |
| **Iron and steel** | production × route SEC × **η 0.70** × fossil share (BF/BOF SEC **4.8 GJ/t** = sinter + rolling only; coke/BF excluded; EAF fuel 2.5 GJ/t) | **0.90** | **1.55** | Low: lean on final-consumption SEC floor. High: raise toward ~7.5 GJ/t; METHODS vs benchmark ≈ **1.55**. |
| **Steam cracking** | ethylene × **35.9 GJ/t** × **η 0.90** × fossil share (total furnace duty: external + byproduct fuel-gas) | **0.47** | **1.00** | Low: external-fuel-only **17 GJ/t** / 35.9 ≈ 0.47. High = base: full duty required for electrification. |
| **Chemicals** | product SEC × η × fossil share (e.g. ammonia fuel-only 9 GJ/t × 0.90; soda ash 10 GJ/t × 0.85) | **0.85** | **1.40** | Low: SEC/η lean. High: METHODS vs Hotmaps ≈ **1.40**. |
| **Pulp and paper** | production × **10.5 GJ/t** × **η 0.85** × country fossil share | **0.70** | **1.15** | Low: higher biomass / lower fossil share (~0.1–1.0 by country). High: SEC + fossil-share upside (~+15%). |
| **Food, beverage, tobacco** | fuel_TJ = CO₂e / **58.2**; useful = fuel_TJ × **0.85**; then × country scale to IndustryHeat-EU | **0.85** | **1.40** | Residual rescale/allocation error after country matching (not unscaled CT). |
| **Textiles, leather, apparel** | Same emissions inversion as food (EF 58.2, boiler η 0.85), **no** country rescale | **0.85** | **1.20** | Fuel EF and gas–oil mix (±); narrower than food. |
| **Aluminium** | production × alumina/Al SEC × η × fossil share (e.g. Bayer ~11 GJ/t alumina × 0.85) | **0.90** | **1.15** | METHODS vs Hotmaps ≈ **1.11**; tight band. |

General production×SEC form: `useful_heat = production × SEC × η × fossil_share`.
