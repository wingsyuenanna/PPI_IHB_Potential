# Fossil share module

Two layers, both keyed to **Climate TRACE subsector categories**:

1. **Subsector-level fossil share (data-driven, primary).**
   `compute_fossil_share.py` → `fossil_share_by_subsector.csv`.
   Computed from Eurostat `nrg_d_indq` 2024 (fuel by NACE×country) via the
   Climate TRACE→NACE map, cross-checked with `Input/eprtr_nace_mapping.csv`.
   `apply_fossil_share.py` joins it onto the facilities and writes
   `facilities_2024_eu_replaceable.csv` with `replaceable_heat_mwh =
   useful_heat_mwh × fossil_share`. **This is the validated layer to use.**
   - `fossil_share` = fossil_fuel / (fossil_fuel + biomass_fuel); electricity &
     derived heat excluded (useful_heat is combustion-derived).
   - Country values where Eurostat reports a disaggregated TOTAL; unreliable
     slices (suppressed biomass → spurious ~1.0, e.g. Sweden pulp & paper) fall
     back to the robust EU-27 aggregate. UK/GBR (absent from Eurostat) also
     falls back.
   - EU-27 result: pulp & paper 0.43 (black liquor), cement/lime 0.84 (alt
     fuels), food 0.89, glass/steel/aluminium ~1.0. Facility-weighted pulp &
     paper drops to ~0.35 once Nordic/Iberian country shares apply.

2. **Temperature-band shape (optional refinement, below).**
   `fossil_share_by_band.csv` adds the *temperature distribution* of fossil
   share. Left OUT of the applied workflow by choice — combine it only if you
   need per-band replaceable heat. When you do, reconcile its level to the
   subsector share from layer 1 (formula at the end of this file).

---

## Layer 2: fossil share by subsector × temperature band

`fossil_share_by_band.csv` gives, for each subsector and each of the five
temperature bands (`<100`, `100-200`, `200-500`, `500-1000`, `>1000` °C), the
fraction of **useful process heat in that band that is fossil-fired** — i.e. the
share that is a target for electrified heat batteries. It excludes biomass /
black liquor / renewable-waste heat and already-electric heat.

Downstream use (per facility):

```
replaceable_heat = Σ_band  useful_heat
                          × band_share[subsector, band]      # from heat_temperature_bands.py
                          × fossil_share[subsector, band]    # this table
                          × replace_frac[band]               # battery-servability (steam-suitable)
```

## Provenance and honesty note

**These are literature-informed estimates of the temperature *shape* of fossil
share, NOT verbatim cells from the Rehfeldt/FORECAST dataset.** Rehfeldt et al.
2018 (and the FORECAST model) publish two *marginals* — heat by
subsector×temperature, and energy carrier by subsector/country — but do **not**
publish the joint carrier×temperature×subsector cube (they state cross-references
exist but keep them inside the model). No statistical source reports, e.g., "gas
consumed below 100 °C." So this table is synthesised from:

1. **Temperature-band shape** — the hotmaps `industryBenchmarks_2014.csv` band
   shares already in this repo (Fraunhofer ISI; cites Fleiter, Arens, Rehfeldt,
   McKenna).
2. **Carrier / fossil level** — Eurostat subsector fuel mix (the existing
   `fossil_share` country×NACE lookup) as the anchor.
3. **Process→fuel→band knowledge** — which processes within a subsector are
   fossil vs biomass and where they sit (cement/lime kilns = coal/petcoke + alt
   fuels; pulp recovery boiler = black liquor; cracker = fossil tail-gas; glass
   melt = gas; food/textiles = gas steam).

Sources consulted:
- Rehfeldt, Fleiter et al. 2018, *A bottom-up estimation of the heating and
  cooling demand in European industry*, Energy Efficiency 11:1057.
  DOI 10.1007/s12053-017-9571-y. Headline temperature split: >500 °C 1035 TWh
  (iron & steel), 100–500 °C 706 TWh (chemical steam), <100 °C 228 TWh (food).
- Naegler et al. 2015, *Quantification of the European industrial heat demand
  by branch and temperature level*, Int. J. Energy Res. 39:2019.
- Cembureau / ECRA: EU cement alternative-fuel thermal substitution (~48 %,
  roughly half biogenic) — why the cement kiln band is ~0.70, not ~1.0 fossil.
- CEPI: EU pulp & paper biomass self-supply (why P&P is country-driven).

## REQUIRED reconciliation step (keeps you tied to validated totals)

The `fossil_share` values here carry the temperature *pattern*; the *level* must
be re-anchored per facility to the Eurostat country×subsector fossil share so the
heat-weighted mean over bands reproduces the validated national number:

```
scale = eurostat_fossil_share[country, subsector]
        / Σ_band ( band_share[subsector, band] × fossil_share[subsector, band] )
fossil_share_reconciled[band] = clip( fossil_share[band] × scale, 0, 1 )
```

This preserves the shape (glass high-band-heavy, food low-band-heavy) while the
absolute fossil level stays validated by Eurostat. **Pulp & paper rows are
flagged `confidence = country`: do not use the shape at all — take the country
value directly, because biomass and fossil both serve the same steam bands and
temperature does not separate them.**

## Confidence column

- `country` — placeholder; override entirely with the Eurostat country value.
- `med` — grounded in a clear process/fuel structure (kilns, furnaces, steam).
- `low` — band carries little heat for this subsector, or fuel split is
  genuinely uncertain; value is an informed extrapolation.

## The pattern you expected (confirmed)

- **Low-band-fossil subsectors** (food, textiles, chemicals steam): fossil
  concentrated <200 °C because that is where their gas-fired steam sits.
- **High-band-fossil subsectors** (glass, cement, lime, steel, cracking): fossil
  concentrated >500 °C — melting/kiln/furnace duty. Cement/lime are pulled
  *down* from ~1.0 by alternative fuels; glass/steel/cracking stay ~0.9.
