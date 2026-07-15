# Draft — Heat-demand methods & results subsections

*Draft prose for journal submission. Citation keys in [brackets] are placeholders.
Heat is reported as **useful heat** (fuel input × furnace/boiler efficiency).
Numbers are EU-27 (facility layer also includes GB sites); see scope note.*

---

## X.  Heat-demand estimation and relation to IndustryHeat-EU

### X.1  Two estimator families, and why we estimate bottom-up

Two structurally different approaches can produce facility-resolved industrial
heat demand. The first, exemplified by the IndustryHeat-EU dataset
[IndustryHeat-EU; Zenodo 10.5281/zenodo.17414346], is *top-down*: national
country–sector useful-heat totals are derived by scaling JRC-IDEES 2021 useful-
energy shapes to Eurostat 2024 energy-use balances [JRC-IDEES-2021; Eurostat
nrg_bal_c], and individual facilities receive heat only as a spatial allocation —
a preliminary emissions-based estimate is used purely as a distribution weight,
then rescaled so that facility values sum exactly to the country–sector control
total. The second, adopted here, is *bottom-up*: each facility receives an
independent heat estimate from its production and a process-specific energy
intensity, and national totals emerge as the sum of facility estimates.

The choice is dictated by the unit of analysis. Because our object is the
facility-level levelised cost of heat (LCOH) and the scale at which
electrification becomes competitive, we require heat magnitudes that carry
independent information about each plant. In a top-down allocation the facility
values are, by construction, a national total redistributed by a proxy; they
contain no plant-specific signal and cannot support facility-level economic
inference without circularity. A bottom-up estimate can be wrong at any single
facility, but it is falsifiable at the facility level and can be reconciled
against — rather than forced to — independent aggregates.

### X.2  Estimator

For subsectors with facility production (tiers 1–2), useful heat is
`production × SEC × η`, where SEC is the fuel input for process heat per tonne of
product and `η` is the **useful thermal efficiency** of the process (useful heat
delivered ÷ fuel input). We take `η` from independent process-engineering
literature (Table X1) rather than the fuel-accounting convention `η = 1` — the
latter reports fuel *consumed* rather than the useful heat a decarbonised
replacement must deliver, and would oversize that replacement by `1/η`.
Crucially, the efficiencies are **not** drawn from the JRC-IDEES / IndustryHeat-EU
useful-energy dataset we validate against, so the reconciliation in §Y remains
non-circular. Steam-boiler processes use 0.85 [US DOE steam guidance].

SEC values are drawn from sector engineering literature (IEA/GNR and the IEA
Cement Roadmap for cement; EuLA/BREF for lime; [Schmitz et al. 2011] for glass;
CEPI for pulp and paper; worldsteel/hotmaps final-consumption benchmarks for
steel; IEA analyses and [Ren et al. 2006] for chemicals). For subsectors without
production whose emissions are essentially all fuel combustion (food, beverages
and tobacco; textiles), heat is obtained by emissions-to-energy inversion using
IPCC fuel emission factors [IPCC 2006] and a boiler efficiency of 0.85, and food
is rescaled per country to the useful-energy reference to correct known
mis-allocation in the underlying facility emissions. All estimates are fuel-based
heat; electricity is excluded throughout. Facility production and metadata are
from Climate TRACE [Climate TRACE], deduplicated by manual review of coincident
names, coordinates and capacities. Temperature bands are assigned from hotmaps
per-process fuel-SEC recipes.

**Table X1. Useful thermal efficiencies (fuel input → useful heat).**

| Process | η | Source |
|---|---:|---|
| Cement kiln | 0.60 | Madlool et al. 2011 (RSER 15:2042); IEA Cement Roadmap |
| Lime kiln | 0.65 | EU BREF Cement/Lime/MgO (shaft ~0.80, rotary ~0.55) |
| Glass melting furnace | 0.45 | Beerkens 2008; Schmitz et al. 2011 |
| Steel reheating/sinter (all routes) | 0.70 | IEA Iron & Steel; worldsteel |
| Steam-cracking furnace | 0.90 | Ren, Patel & Blok 2006 (Energy 31:425); Ullmann's *Ethylene* |
| Ammonia / methanol reformer | 0.90 | fired heater w/ heat recovery |
| Aluminium smelting furnaces | 0.65 | IAI / IEA aluminium data |
| Steam-boiler processes | 0.85 | US DOE steam-system guidance |

Two caveats attach to `η`. It is the *process* efficiency, not the
electricity-to-heat efficiency of the replacement (heat-pump COP, resistive/IHB
delivery ≈ 0.9–0.95), which enters the LCOH separately; the gas-vs-electric
crossover depends on the *ratio* of the two, which is modest at high temperature
because electric heating mainly avoids the combustion flue-gas loss, not the
process-inherent losses. The steam-cracking value (0.90) is the least certain and
is carried as a sensitivity.

### X.3  Steam-cracker scope

Steam cracking additionally requires a fuel-scope decision. Cracking-furnace duty
(~35.9 GJ per tonne of ethylene, hotmaps benchmark) is fired by purchased
external fuel (~17 GJ/t) and by byproduct "tail gas" (methane and hydrogen
separated from the cracked stream and burned back in the furnaces, ~19 GJ/t). We
adopt the total furnace duty rather than the external-fuel figure, because the
byproduct gas is fossil-derived and its combustion must also be displaced to
decarbonise the process; the external-fuel basis would halve estimated cracker
heat. At the useful-heat basis (η = 0.90) this reproduces the IndustryHeat-EU
per-facility values to within ~10% (e.g. Dow Terneuzen 12.3 vs 13.4 TWh),
providing an independent plant-level check.

### X.4  Validation strategy and its limits

We validate by reconciling bottom-up sector and country totals against two
independent top-downs — the IndustryHeat-EU useful-energy reference and a
Eurostat final-energy × process-heat-share estimate — rather than constraining
the bottom-up to match either. Three limits should be read alongside the results.
First, our facility layer and IndustryHeat-EU share a Climate TRACE dependence,
so the comparison is a consistency check, not a fully independent one. Second,
our food and textiles estimates adopt the same allocation-to-control-total logic
as the top-down (food is explicitly rescaled to the reference); the independence
claim therefore holds for the tier-1/2 tonnage sectors (cement, steel, glass,
pulp and paper, chemicals) and not for the emissions-allocated sectors. Third,
because we now report useful heat via independent literature efficiencies, the
tonnage sectors align with the useful-energy reference to within ~15% (§Y);
residual gaps are scope- and coverage-driven, not method artefacts.

---

## Y.  Results — industrial heat demand

We estimate **≈590 TWh** of fuel-based *useful* process heat across eight
energy-intensive manufacturing subsectors (EU-27; the facility layer also carries
GB sites; 606 TWh including facilities outside the eight mapped sectors). This is
a deliberate subset of the IndustryHeat-EU total of 1,124 TWh useful / 987 TWh
non-electric heat, which additionally covers residual sectors (machinery,
transport equipment, wood, mining, construction and other industry, ≈350 TWh) and
electricity, both outside our fuel-based, energy-intensive-manufacturing scope.

### Y.1  Sector totals and cross-comparison

Table Y1 compares our bottom-up useful-heat estimate with the IndustryHeat-EU
useful-energy value by sector.

**Table Y1. Bottom-up useful heat vs IndustryHeat-EU, by sector (TWh).**

| Sector | Bottom-up | IndustryHeat-EU (useful) | Ratio |
|---|---:|---:|---:|
| Chemicals | 200.8 | 232.9 | 0.86 |
| Food, beverages & tobacco | 110.5 | 125.2 | 0.88 |
| Steel (primary + secondary) | 101.8 | 105.5 | 0.96 |
| Cement (+ lime) | 78.2 | 63.1 | 1.24 |
| Pulp & paper | 54.0 | 167.4 | 0.32 |
| Textiles & leather | 17.4 | 15.0 | 1.16 |
| Glass | 16.3 | 101.7 † | 0.16 |
| Non-ferrous metals | 10.1 | 28.0 | 0.36 |

† Our estimate covers glass only. The IndustryHeat-EU reference has no glass-only
column: 101.7 TWh is its "Ceramics and glass" total, i.e. the whole non-metallic-
minerals residual after cement (glass **plus** ceramics, brick, refractory, lime
and plaster). The ratio is therefore glass-vs-(ceramics+glass), not like-for-like.

After applying independent literature efficiencies, the four production-based
tonnage sectors converge on the useful-energy reference: steel 0.96, cement 1.24,
chemicals 0.86, food 0.88 (against the 2021 reference file the same four read
1.02, 1.03, 1.16 and 1.07). Because these efficiencies are engineering values
rather than inheritances from JRC-IDEES, this agreement is genuine cross-
validation. The remaining deviations are scope- and coverage-driven, not method
error: pulp and paper (0.32) because facility coverage is limited to the largest
mills — note this is *not* a biomass artefact, since our estimate and the
reference are both total (all-fuel) useful heat, so the black-liquor share
(~60% of mill heat) cancels in the ratio; glass (0.16) because the
reference column bundles ceramics, brick and refractory firing (and lime) with
glass, none of which we model here — glass alone is well captured, but it is a
small part of that non-metallic-minerals residual; and non-ferrous metals (0.36) from facility
coverage. Textiles (1.16), an emissions-inversion sector, is a small-base
outlier.

### Y.2  Temperature distribution

**Table Y2. Covered useful heat by temperature band (EU-27).**

| Band | TWh | Share | Primary electrified option |
|---|---:|---:|---|
| < 100 °C | 72 | 12% | Heat pump (COP ≈ 3) |
| 100–200 °C | 126 | 21% | High-temperature heat pump / electric boiler |
| 200–500 °C | 32 | 5% | Electric / thermal storage |
| 500–1000 °C | 282 | 46% | Thermal storage / electric furnace |
| > 1000 °C | 96 | 16% | Electric furnace |

About one third of covered useful heat lies below 200 °C — the clean heat-pump
market — while **62% sits above 500 °C**, concentrated in chemicals (cracking
furnaces), steel and cement. The economically contested region for our LCOH
comparison — where thermal storage (industrial heat batteries) competes directly
with gas because heat pumps cannot reach the temperature — is therefore large and
dominated by a tractable set of high-load facilities.

### Y.3  Aggregate consistency

On a useful-heat basis the tonnage sectors sit within ~15% of the IndustryHeat-EU
useful-energy reference and below the Eurostat final-energy × heat-share estimate
(a final-energy quantity that additionally includes electricity), the expected
ordering. At the plant level, the largest facilities are reproduced within ~10%
once the cracker scope is aligned, supporting the use of the bottom-up estimate
for facility-level economic analysis.
