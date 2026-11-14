# Industrial heat-pump CAPEX (EU use case; US sources labeled)

Scope: installed or quoted capital cost per kW of **thermal output** for (1) low-temperature industrial heat pumps, hot water below 100 °C, and (2) medium-temperature / steam heat pumps, roughly 100–200 °C. Fixed O&M is recorded only when the same source states it. Electric boilers and thermal storage are separated from heat-pump equipment. Numbers below are copied from the cited documents; none were inflated or FX-converted in these notes.

The user’s baseline (Jeffrey Rissman 2022 / Agora Energiewende basis, **2021 USD**: $700/kW_th below 100 °C and $870/kW_th for 100–200 °C; FOM $12 and $18 per kW_th-year) is a comparison point only. It was not re-derived here.

## What CAPEX ranges do catalogues and reviews report?

### Takeaway

Published figures for industrial heat pumps span about **200–1,500 €/kW_th** before full process integration, and about **700–2,000 €/kW_th** once installation, steam hardware, or a large temperature lift is included. The Danish Energy Agency’s January 2026 process-heat catalogue is the clearest EU installed-cost anchor for 100–150 °C: **1.20–1.55 M€/MW_th** (2025 €) for hot water, **1.40–1.75 M€/MW_th** for steam, plus **0.20 M€/MW** if the lift exceeds 75 K. Costs below 100 °C cluster nearer **0.4–0.9 M€/MW_th** (about $250–800/kW_th in US studies) when the quote is a single-stage unit on waste heat. The Rissman 2021-USD pair ($700 / $870 per kW_th) sits inside the older and equipment-leaner band, and below the 2026 Danish installed costs for steam and high lift.

### Cited Findings

**Danish Energy Agency, Technology Data for Industrial Process Heat, January 2026 revision (2025 price level, EUR).** Financial data in this catalogue edition are real euros at the **2025** price level, excluding VAT. Nominal investment is an overnight / EPC-style cost per MW of heat: equipment plus installation (engineering, civil works, buildings, on-site grid connection, commissioning). Owners’ development costs, interest during construction, lost production, and dismantling are excluded. Cost of an *additional* supply system (for example a new hot-water circuit) is indirect investment, not in the nominal figure. — [DEA process-heat catalogue PDF](https://ens.dk/media/7757/download); catalogue page [ens.dk](https://ens.dk/en/analyses-and-statistics/technology-data-industrial-process-heat)

High-temperature heat pumps (defined there as supply **above 100 °C**, hot water). Investment “includes the heat pump, necessary piping to existing hot water or steam loop, and minimal construction work.” Extra cost from an inadequate electrical connection is excluded. Indirect cost of converting a steam circuit to hot water is called highly uncertain and is **not** in the table.

| Supply | 2025 | 2030 | 2040 | 2050 | Unit |
| --- | --- | --- | --- | --- | --- |
| Hot water up to 125 °C | 1.20 | 1.15 | 1.05 | 1.00 | M€/MW_heat |
| Hot water up to 150 °C | 1.55 | 1.50 | 1.40 | 1.35 | M€/MW_heat |
| Steam up to 125 °C | 1.40 | 1.30 | 1.15 | 1.10 | M€/MW_heat |
| Steam up to 150 °C | 1.75 | 1.65 | 1.50 | 1.45 | M€/MW_heat |

Steam table is described as the hot-water cost plus about 15% for more expensive materials, especially the steam-generating heat exchanger. Worked example, 2 MW, source 60 °C, sink 140 °C steam (lift 80 K): start from 1.55 M€/MW (equipment and installation, up to 150 °C), add 0.20 M€/MW steam equipment and 0.20 M€/MW for lift above 75 K → **1.95 M€/MW** (3.90 M€ for 2 MW). A cascade (lift above ~70 °C) is described as almost twice a single-stage system in **equipment** cost. — [DEA process-heat catalogue PDF](https://ens.dk/media/7757/download); revision note [January 2026](https://ens.dk/media/7778/download)

**Same catalogue, earlier edition (financial-data section: fixed 2019-level EUR; an earlier guideline paragraph in the same PDF still says fixed 2015 prices — internal inconsistency).** Hybrid absorption/compression heat pumps (HACHP), nominal investment **including installation**:

| Supply | 2020 | 2030 | 2040 | 2050 |
| --- | --- | --- | --- | --- |
| up to 125 °C | 0.87 M€/MW_heat | 0.78 | 0.73 | 0.70 |
| up to 150 °C | 1.05 M€/MW_heat | 0.93 | 0.88 | 0.84 |

The 150 °C row was marked up for low commercial availability (process contingency 10% and project contingency 10%). INNOTERM (interview 24 Nov 2017) is cited for HACHP investment about **20% above** ordinary vapour-compression heat pumps. The steam-booster chapter uses **0.73 M€/MW** as the traditional heat-pump subsystem cost “similar to the one in the chapter for traditional heat pump,” plus evaporator 0.03 M€/MW and steam compressors 0.33 M€/MW → subsystems 1.09 M€/MW; first-of-a-kind corrected cost **1.63 M€/MW in 2020** for a ~4 MW cascade to ~150 °C / ~5 bar steam from a 30/20 °C source. That booster system was then TRL ~4 and not commercial. — [Earlier DEA process-heat PDF](https://ens.dk/media/3307/download)

The traditional-heat-pump **datasheet** (60/70/80 °C hot water, typical unit 0.5–5 MW) is not printed in the narrative PDF; both editions say “see separate Excel.” The 0.73 M€/MW figure above is the only explicit traditional-unit number found in the narrative. The January 2026 narrative still says an 80 °C hot-water circuit, if the site does not already have one, must be **added** to the basic heat-pump cost and can dominate feasibility. — [DEA 2026 PDF](https://ens.dk/media/7757/download)

**IEA HPT TCP Annex 58 Task 1 technology report (Zühlsdorf / Danish Technological Institute; supplier survey, circa 2022–2023).** 34 high-temperature heat-pump technologies, TRL 4–9, capacities 30 kW to 70 MW, maximum supply 100–280 °C. Specific investment **200–1,500 €/kW**, defined as the supplier range “for installed system **without integration**.” Suppliers provided the figures; they were **not third-party validated**, and low-TRL cases include cost targets. For technologies that stated a cost, the band excluding installation and integration is **200–1,200 €/kW**, mean temperature lifts about 20–190 °C. A higher lift tends to cost more. A weak tendency toward lower cost at lower maximum supply temperature, except steam MVR. **No clear correlation with capacity** in the supplier quotes, because each quote already mixes size and application. — [Annex 58 Task 1 report](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf); summary slides [Zühlsdorf, 15 May 2023](https://heatpumpingtechnologies.org/content/uploads/sites/70/2023/09/20230515-iea-hp-conference-hthp-workshopmerged.pdf)

Illustrative supplier bands repeated in Annex 58 / DTI market slides (EUR/kW, no separate currency year; “spec. invest. cost”): Hybrid Energy (NH3/water, 0.5–5 MW, Tmax 120 °C, TRL 9) **200–600**; Siemens Energy turbo (8–70 MW, up to 160 °C) **250–800**; Heaten piston (up to ~165–200 °C) **250–350** or **280–450** depending on the slide vintage; Enerin Stirling-type (up to 250 °C, TRL ~6–7) **600–800**; Olvondo HighLift (up to 200 °C) **1,200**; Weel & Sandvig steam turbo MVR **150–250**; SPH Thermbooster **150–1,000**; Qpinch heat transformer (heat-driven, not a vapour-compression heat pump) **1,000–2,000**. — [Annex 58 report](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf); [Arpagaus, ACEEE workshop, 11 July 2023](https://www.aceee.org/sites/default/files/pdfs/IHP_Workshops_2023/Cordin_Arpagaus_-_OST.pdf); [Poulsen / DTI, NEFI, 3 Apr 2024](https://www.nefi.at/files/media/Bilder/News/2024-03%20Industrielle%20Abwa%CC%88rmenutzung%20mit%20Hochtemperaturwa%CC%88rmepumpen/Jonas%20Lundsted%20Poulsen_NEFI%20Technology%20Talk%20-%20High-Temperature%20Heat%20Pump%20Market%2C%20DTI%20-%2003-04-2024.pdf)

Hybrid Energy fact sheet (Annex 58): “Specific investment cost for installed system **without integration**: From **200 €/kW** up to **600 €/kW** depending of the effect and the number of compressors,” capacity 0.5–2 MW reciprocating or 1–5 MW screw, sink temperatures in the ~120 °C class. — [Hybrid Energy Annex 58 sheet](https://heatpumpingtechnologies.org/content/uploads/sites/70/2022/07/annex58-hybrid-energy-juli-2022-rev3.pdf)

**Swiss HTHP case quotes (Spiess / SWEET, 7 Nov 2024), equipment excluding planning and integration.** Design point about 550 kW, sink 20/115 °C (1.5 bara steam), source 50/45 °C, lift 65 K. Quoted specific investment **840–1,000 EUR/kW** for HFO machines and **1,300 EUR/kW** for n-butane. Example offers: Combitherm ~540 kEUR on ~0.5 MW class; ThermBooster ~550–650 kEUR on 652 kW; n-butane unit 830–850 kEUR on 634 kW. The same slide uses a **planning and integration cost factor of 2.0** and a maintenance factor of **0.04** of capital cost. — [Spiess case-study slides](https://www.sweet-decarb.ch/fileadmin/downloads/Presentations_File/2024_11_07_HTHP_webinar_Gustav_Spiess_Case_Study.pdf)

**Zühlsdorf, Bühler, Bantle, Elmegaard (2019), process heat above 150 °C (extends past 200 °C; supply cases up to 280 °C).** Bottom-up total capital investment: cascade COP 1.9 in both cases; specific TCI **946 €/kW** and **966 €/kW** on the ~50 MW alumina cases, and **1,997 €/kW** and **1,868 €/kW** on the ~8 MW spray-dryer cases (cascade vs reversed Brayton). Currency year is the paper’s own costing year (published 2019); not restated as a price base in the extracted text. — [DTU orbit PDF](https://backend.orbit.dtu.dk/ws/files/195360755/Analysis_of_technologies_and_potentials_for_heat_pump_based.pdf)

**Kosmadakis et al., Energy Conversion and Management (2020) — paywalled; abstract/secondary citation only.** The abstract, as quoted on ScienceDirect, says published specific costs are “usually in the range of **200 to 800 EUR/kW**,” and that Meyers et al. found about **300 to 900 EUR/kW** above 100 kW_th and **below 600 EUR/kW** for large systems. Full paper not read. — [ScienceDirect abstract](https://www.sciencedirect.com/science/article/abs/pii/S0196890420310207)

**ACEEE, Rightor, Scheihing, et al., March 2022 (United States).** Total installed capital per kW of heat delivered (Qsink). Dollar year is **not stated**; report date is March 2022. Economic scenario is a single stage and lift under about 40 K; technical scenario is at least 50% higher to cover an added compressor stage and complexity.

| Type | Economic, $/kW heat | Technical, $/kW heat |
| --- | --- | --- |
| MVC closed cycle | 400 | 800 |
| MVR semi-open | 325 | 650 |
| MVR open | 250 | 500 |
| TVR (steam thermocompressor; lift typically &lt;15–20 °C) | 150 | n/a |
| Heat-activated Type 1 (absorption) | 1,000 | 1,500 |
| Heat-activated Type 2 (heat transformer) | 1,250 | 1,875 |

MVC economic cost is Arpagaus (2020) **raised** for design and installation. MVR references De Boer et al. (2020), also raised. Maintenance is **3% of CapEx per year** for MVC and MVR, 1% for TVR, 2% for heat-activated types — not a separate $/kW-year. Body text summarizes vapour-compression installed cost as **$250–800 per kW** of heat delivered. — [ACEEE ie2201 PDF](https://www.aceee.org/sites/default/files/pdfs/ie2201.pdf)

**NREL, Cox et al., NREL/TP-7A40-84560, August 2023 (United States).** Default case: 1 MW_th, sink 120 °C, source available 50 °C, refrigerant R1234ze(Z). Specific capital cost **$300/kW_th** for the heat pump, **$30/kW_th** for the gas boiler, **$100/kW_th** for electro-resistive heat. Fixed O&M **$11.8/kW_th-year** for the heat pump (gas boiler $50/kW_th-year; electro-resistive $1.0/kW_th-year). Variable O&M **$0.05/kWh_th** for the heat pump. Authors: costs “taken from the literature or estimated from manufacturing partners” and “should not be used as standards.” Beer-brewing case: steam at 115 °C (10 psi), HTHP capital cost **$800/kW_th**, boiler **$100/kW_th**; a +30% HTHP capital adder is used in one sensitivity for extra integration. Dollar year not labeled beyond the August 2023 report date. — [NREL/TP-7A40-84560](https://docs.nlr.gov/docs/fy23osti/84560.pdf)

**NREL preprint, Akar et al. / OSTI 1862944 (United States, ~2022).** Heat-pump CAPEX scenarios **$150/kW** (low) and **$300/kW** (high) are per **kW of electricity drawn**, not per kW_th, “conservatively consistent with” Kosmadakis et al. (2020) and Meyers et al. (2018). Hybrid solar-thermal plus heat pump is costed separately ($700–850/kW) and is not a heat-pump-only figure. — [OSTI preprint](https://www.osti.gov/servlets/purl/1862944)

**BPA industrial heat pump market study (2024, United States), secondary to ACEEE.** Uses the average of ACEEE MVC economic and technical costs, **$600 per unit of Qsink**, “equipment and installation,” as a scoping estimate. — [BPA PDF](https://www.bpa.gov/-/media/Aep/energy-efficiency/emerging-technologies/202403-industrial-heat-pump-market-study.pdf)

**Pieper et al. via IEA HPT Annex 48 Danish report (district heating, not industrial process heat).** Total project specific cost for Danish large heat pumps: about **0.5–0.8 M€/MW (2014)** and **0.8–1.1 M€/MW (2017)**. Heat-pump equipment is **38–54%** of total investment; the rest is heat-source works and balance of plant. Excess-heat source, total project: **1.30 to 0.97 M€/MW** from 0.5 to 1 MW, **0.97 to 0.72** from 1 to 4 MW, **0.72 to 0.67** from 4 to 10 MW. Groundwater is the expensive source; flue gas is the cheap one. — [Annex 48 Denmark PDF](https://backend.orbit.dtu.dk/ws/files/220010789/Denmark_2019_2.pdf); [Pieper cost-allocation slides](https://backend.orbit.dtu.dk/ws/portalfiles/portal/150813986/CONECT_Pieper_Allocation_of_investment_costs_for_large_scale_heat_pumps.pdf)

**JRC, Heat Pumps in the European Union, JRC144191 (2025/2026).** States upfront cost “from around **EUR 250 to as much as EUR 2,000 per installed kW of thermal capacity**, depending on the type and quality.” The surrounding table and the 7 kW air-water example are **building** heat pumps. Industrial high-temperature heat pumps are discussed qualitatively (paper, pulp) with **no separate industrial €/kW table** in the extracted text. — [JRC144191](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC144191/JRC144191_01.pdf)

**Reform Institute / instrat-style annex “Clean industrial heat” (in-house, not a technology catalogue).** Authors: “inner assumptions, consulted with experts.” Heat pump **500 / 700 / 870 / 1,300 EUR/kW_th** for 0–100 / 100–150 / 150–200 / 200–500 °C. Electric heating that is not a heat pump: **175 EUR/kW_th**. Natural-gas boiler **100 EUR/kW_th**. No currency year. The 870 figure matches the Rissman **2021 USD** number for 100–200 °C with no stated FX conversion, so treat it as secondary and possibly borrowed. — [Annex PDF](https://ireform.eu/s/uploads/Clean_industrial_heat_Electrification_scenarios_for_selected_sectors_ANNEX.pdf)

**Projects.** DryFiciency pilot sheets (Agrana ~374 kW to 138 °C, 2020; Wienerberger ~296 kW to 121 °C design, 2019) list investment as **not disclosed**; they report energy-cost savings only (€42,900/a and €60,500/a). — [Agrana sheet](https://heatpumpingtechnologies.org/content/uploads/sites/81/2026/05/demo4dryfagrana20251008.pdf); [Wienerberger sheet](https://heatpumpingtechnologies.org/content/uploads/sites/70/2022/07/hthpannex58dryfwbgfinal-1.pdf). No public €/kW_th for SPIRIT or Push2Heat was found in this pass.

**IEA, The Future of Heat Pumps (2022).** Upfront costs cited are residential/commercial (air-to-air about USD 3,000–6,000 per installation). No industrial €/kW or $/kW_th CAPEX. Investment totals (USD 350 billion in 2030, real 2021 dollars) are buildings, not factories. — [IEA PDF](https://iea.blob.core.windows.net/assets/4713780d-c0ae-4686-8c9b-29e782452695/TheFutureofHeatPumps.pdf)

**Not heat pumps.** DEA direct-firing chapter, 2025 prices: electric heating **element** specific cost **0.060 M€/MW** (67% equipment / 33% installation), capacity 1–10 MW; this is the burner/element only, not process equipment and not an electrode steam boiler. Electrode/resistance **steam and hot-water boilers** have their own chapter (to 60 MW, typical Danish steam 8 bar / 175 °C); grid cable from the medium-voltage network is excluded, but the €/kW figure sits in the Excel datasheet and was **not** in the narrative extract. NREL’s electro-resistive **$100/kW_th** and gas boiler **$30/kW_th** are in the same table as the $300/kW_th heat pump and must not be mixed into the heat-pump range. MVR evaporator costs in the DEA catalogue are in **€ per m³/day of water**, not €/kW_th. Annex 58 mentions Carnot batteries / pumped thermal storage as a **different** system that can *use* an HTHP as the charger. — [DEA PDF](https://ens.dk/media/7757/download); [NREL 84560](https://docs.nlr.gov/docs/fy23osti/84560.pdf); [Annex 58](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf)

### Inferences

- A defensible **equipment-only** band for commercial HTHPs (about 100–160 °C, multi-MW, Europe, early 2020s supplier quotes) is roughly **200–800 €/kW_th**. Adding installation and a steam generator, or a lift above ~70–75 K, moves the same machines toward **1,200–2,000 €/kW_th** in the 2026 Danish catalogue and the Swiss integration factor of 2.
- The jump from the 2019/2020 Danish HACHP table (0.87–1.05 M€/MW) to the 2026 table (1.20–1.55 M€/MW hot water) is larger than Danish inflation over that period. Treat it as a **re-estimate of scope and market quotes**, not as a pure price-index update. The 2026 edition also says a “broader range of low-CAPEX technologies” is emerging, which is in tension with the higher central table.
- Rissman’s $700 and $870 per kW_th (2021 USD) line up with ACEEE’s US economic MVC ($400) to technical MVC ($800), with the older Danish traditional-unit **0.73 M€/MW**, and with the low end of Annex 58. They do **not** line up with DEA 2026 steam-plus-high-lift (**1.95 M€/MW**, 2025 €) or with small-unit bottom-up costs near **1,900 €/kW** above 150 °C.

### Gaps

- The DEA Excel datasheets (traditional 60/70/80 °C heat pump nominal investment, fixed O&M, and electric-boiler €/kW) were not opened. Only narrative cross-references (0.73 M€/MW traditional; FOM field defined but not filled in the PDF) are available.
- Arpagaus et al., Energy 2018 (DOI 10.1016/j.energy.2018.03.166) is paywalled here; manufacturer costs used above are from the 2023 workshop slides, not from a re-read of the 2018 paper.
- No BNEF CAPEX table was found in public documents (only an electricity-price competitiveness remark on a DTI slide).
- Push2Heat and SPIRIT public pages reviewed via search did not yield a project €/kW. DryFiciency pilots withhold investment.
- IEA *Future of Heat Pumps* does not contain industrial equipment CAPEX.

## Which sources are primary?

### Takeaway

Use the **Danish Energy Agency process-heat catalogue (January 2026, 2025 euros)** and **IEA HPT Annex 58 supplier sheets** as the primary EU pair: the first for a consistent installed-cost trajectory, the second for the un-integrated equipment range and the lift effect. ACEEE 2022 and NREL 2023 are the primary **US** public numbers and should stay labeled as US. JRC’s 250–2,000 €/kW and the Reform Institute 500/700/870/1,300 table are not primary industrial equipment costs.

### Cited Findings

- **Primary, EU, catalogue:** Danish Energy Agency & Energinet, Technology Data for Industrial Process Heat. First published April 2020; HTHP and steam-generating chapters revised January 2026 by Danish Technological Institute (Andersen & Holdt) and Viegand Maagøe. Price level 2025 € in the current guideline. — [ens.dk](https://ens.dk/en/analyses-and-statistics/technology-data-industrial-process-heat), [PDF](https://ens.dk/media/7757/download)
- **Primary, EU, technology survey:** IEA Heat Pumping Technologies TCP Annex 58 Task 1, operating agent Benjamin Zühlsdorf, DTI. Supplier-reported costs, explicitly not independently audited. — [Task 1 PDF](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf)
- **Primary, academic bottom-up (above 150 °C, up to 280 °C):** Zühlsdorf et al. 2019, *Energy Conversion and Management*. — [PDF](https://backend.orbit.dtu.dk/ws/files/195360755/Analysis_of_technologies_and_potentials_for_heat_pump_based.pdf)
- **Primary, observed projects, but district heating:** Pieper et al. 2018, summarized in IEA HPT Annex 48 Task 2 Denmark. — [PDF](https://backend.orbit.dtu.dk/ws/files/220010789/Denmark_2019_2.pdf)
- **Primary, United States, installed-cost scenarios:** ACEEE report ie2201, March 2022. — [PDF](https://www.aceee.org/sites/default/files/pdfs/ie2201.pdf)
- **Primary, United States, model defaults with an explicit warning not to treat them as standards:** NREL/TP-7A40-84560, August 2023. — [PDF](https://docs.nlr.gov/docs/fy23osti/84560.pdf)
- **Manufacturer / project quotes (primary as quotes, narrow scope):** Hybrid Energy 200–600 €/kW without integration; Swiss 2024 offers 840–1,300 €/kW excluding planning and integration. — [Hybrid Energy sheet](https://heatpumpingtechnologies.org/content/uploads/sites/70/2022/07/annex58-hybrid-energy-juli-2022-rev3.pdf); [Spiess slides](https://www.sweet-decarb.ch/fileadmin/downloads/Presentations_File/2024_11_07_HTHP_webinar_Gustav_Spiess_Case_Study.pdf)
- **Secondary or out of scope:** JRC144191 building-dominated 250–2,000 €/kW; Reform Institute in-house 500/700/870/1,300; BPA $600/Qsink (average of ACEEE); Kosmadakis 2020 abstract’s 200–800 €/kW literature range; IEA WEO heat-pump special report (buildings). IRENA was not found with an industrial heat-pump €/kW_th table in this pass. EHPA is cited by DEA as “Large scale heat pumps in Europe, 2019” but that report’s cost table was not extracted.

### Inferences

- For an EU industrial facility model, weight **DEA 2026** for the central installed cost at 100–150 °C and **Annex 58** for the low (equipment, no integration) tail. Use ACEEE/NREL only as a US cross-check, not as the EU central value.
- Do not average JRC’s 250–2,000 band with industrial figures; the low end is residential equipment.

### Gaps

- EHPA 2019 large-scale heat pump cost tables, IRENA industrial heat costs, and any public BNEF CAPEX were not retrieved.
- Arpagaus 2018 journal review: paywalled; 2023–2024 slide decks used instead.

## What is included in the quoted CAPEX?

### Takeaway

The same “€/kW” label covers at least four scopes. Equipment-only or “installed without integration” is often **200–800 €/kW**. Danish nominal investment adds installation and short tie-ins to an **existing** loop (**about 1.2–1.8 M€/MW** at 100–150 °C in 2025 €). Full process integration (new hot-water circuit, steam-to-water conversion, planning) can **about double** equipment cost in the Swiss example. Grid reinforcement is regularly excluded. Thermal storage and electric boilers are separate line items.

### Cited Findings

- **DEA nominal investment:** equipment (components, machinery, environmental facilities) plus installation (engineering, civil, buildings, on-site connection, commissioning). Excludes VAT, owner’s pre-development, interest during construction, lost production, decommissioning, and a new off-plot supply system. HTHP chapter further limits inclusion to the heat pump, piping to an **existing** hot-water or steam loop, and minimal construction; **excludes** an undersized electrical connection. Steam hardware is an explicit adder (0.2 M€/MW in the worked example; the steam table itself is ~15% above hot water). Lift above 75 K is another explicit adder (0.2 M€/MW). Indirect steam-to-hot-water conversion is outside the table. — [DEA PDF](https://ens.dk/media/7757/download)
- **Annex 58:** “Range for specific investment cost for installed system **without integration**.” Figure 2-32 caption: specific investment “**disregarding installation and integration cost**.” — [Annex 58 PDF](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf)
- **Hybrid Energy:** “installed system without integration.” — [fact sheet](https://heatpumpingtechnologies.org/content/uploads/sites/70/2022/07/annex58-hybrid-energy-juli-2022-rev3.pdf)
- **Swiss 2024 quotes:** “Specific investment costs (**excl. planning and integration**)”; separate “cost factor for planning & integration = 2.0.” — [Spiess slides](https://www.sweet-decarb.ch/fileadmin/downloads/Presentations_File/2024_11_07_HTHP_webinar_Gustav_Spiess_Case_Study.pdf)
- **ACEEE:** “total installed capital cost”; MVC value deliberately raised above a literature equipment figure “to account conservatively for added design and installation costs.” Technical case adds stage/complexity, not a quantified integration line. — [ACEEE PDF](https://www.aceee.org/sites/default/files/pdfs/ie2201.pdf)
- **NREL 2023:** overnight specific capital cost per kW_th; no financing. One beer-case sensitivity adds 30% “to accommodate the potential need for” extra integration (wording in the extract is truncated after “potential need for”). Not a audited bid. — [NREL PDF](https://docs.nlr.gov/docs/fy23osti/84560.pdf)
- **Pieper / district heating:** total project cost; heat pump itself is only 38–54%. Heat-source wells, sewage works, or flue-gas ducts dominate the rest. Do not import these totals as “heat pump equipment” for a factory that already has a waste-heat stream. — [Annex 48 PDF](https://backend.orbit.dtu.dk/ws/files/220010789/Denmark_2019_2.pdf)
- **Older DEA HACHP 150 °C row:** includes 10% process contingency and 10% project contingency because the temperature was not yet commercial (2020 edition). — [Earlier PDF](https://ens.dk/media/3307/download)
- **Electric boilers / storage:** DEA states electric-boiler CAPEX excludes the new medium-voltage supply cable. Direct-firing electric cost is the heating element only (0.060 M€/MW). NREL stores battery cost as its own result ($45,566 in one beer-case table), not inside the $/kW_th heat-pump cost. — [DEA PDF](https://ens.dk/media/7757/download); [NREL PDF](https://docs.nlr.gov/docs/fy23osti/84560.pdf)

Fixed O&M, only where the CAPEX source also states it:

- NREL 2023 default: **$11.8 per kW_th-year** fixed, plus **$0.05/kWh_th** variable, next to $300/kW_th. — [NREL PDF](https://docs.nlr.gov/docs/fy23osti/84560.pdf)
- ACEEE 2022: **3% of heat-pump CapEx per year** for MVC/MVR (so $12/kW-year if CapEx is $400/kW, or $24/kW-year if CapEx is $800/kW). — [ACEEE PDF](https://www.aceee.org/sites/default/files/pdfs/ie2201.pdf)
- Swiss 2024 case: maintenance factor **0.04** on capital (4%/year), next to 840 €/kW equipment before the integration factor. — [Spiess slides](https://www.sweet-decarb.ch/fileadmin/downloads/Presentations_File/2024_11_07_HTHP_webinar_Gustav_Spiess_Case_Study.pdf)
- DEA defines fixed O&M as € per MJ/s per year (equal to € per MW per year) but the HTHP narrative tables extracted here do **not** fill that cell.

### Inferences

- If the facility model already represents piping, electrical upgrade, and a hot-water loop elsewhere, use Annex 58 / Hybrid Energy / Swiss **pre-integration** quotes. If the model’s CAPEX is the only capital line for the heat pump project, use **DEA nominal investment** (and add 0.2 M€/MW for steam and another 0.2 M€/MW for lift >75 K when those apply).
- Applying the Swiss factor of 2 on top of DEA nominal investment would double-count installation. DEA already includes installation; the Swiss factor is on an equipment quote.
- User FOM of $12 and $18 per kW_th-year (2021 USD) is the same order as NREL’s $11.8 and as 3% of a $400–600/kW machine. It is **lower** than 3% of an $800/kW machine or 4% of a 1,400 €/kW installed machine.

### Gaps

- DEA 2026 fixed O&M for HTHPs was not in the narrative PDF.
- No source in this pass itemizes a standard percentage split (equipment vs installation vs contingency) for the 2026 1.20–1.55 M€/MW figures. The older catalogue’s general rule is only that equipment and installation shares should be reported when known.
- “Integration” is not a standard bill of quantities. Swiss “2.0” and DEA “indirect piping” are not the same scope.

## What low / central / high values are defensible for 2025 and 2030?

### Takeaway

State sensitivities in **2025 euros** for the EU case, using DEA’s own 2025 and 2030 columns, and keep a lower equipment-only case from Annex 58. Do not convert those euros to 2021 or 2025 dollars in the model until an explicit FX and CPI series is applied; that conversion was **not** done here. A 2030 decline of only about **4–8%** versus 2025 is what the current Danish HTHP table itself assumes. The user’s $700 / $870 (2021 USD) remains a reasonable **low-to-central equipment** case, not the high installed-steam case.

### Cited Findings

DEA trajectory, **2025 euros**, M€ per MW_heat (= thousand € per kW), installed, existing-loop tie-in, no grid reinforcement, no steam-system rebuild — [DEA PDF](https://ens.dk/media/7757/download):

- 2025 hot water ≤125 °C: **1.20**; ≤150 °C: **1.55**. Steam: **1.40** and **1.75**. High-lift steam example: **1.95**.
- 2030 hot water: **1.15** and **1.50**. Steam: **1.30** and **1.65**. The high-lift adder of 0.20 M€/MW is stated in the 2025 worked example and is not given a separate 2030 value.

Annex 58 span, early-2020s supplier euros, **without integration**: **200–1,500 €/kW**, with many commercial compression machines inside **200–800 €/kW**. — [Annex 58 PDF](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf)

Older DEA, **2019-level euros** (see price-year caveat above): traditional unit referenced at **0.73 M€/MW**; HACHP 2020 **0.87 / 1.05** and 2030 **0.78 / 0.93** M€/MW including installation. — [Earlier PDF](https://ens.dk/media/3307/download)

US, dollar year unlabeled (report years 2022 and 2023): ACEEE MVC **$400 / $800 per kW_th**; NREL default **$300/kW_th** and beer steam case **$800/kW_th**. — [ACEEE](https://www.aceee.org/sites/default/files/pdfs/ie2201.pdf); [NREL](https://docs.nlr.gov/docs/fy23osti/84560.pdf)

### Inferences

These bands are a reading of the sources above, not a new catalogue. They are for **EU industrial retrofit**, per kW of heat output, **2025 euros** unless noted. “Central” means DEA nominal investment for a multi-MW unit tied to an existing loop. “Low” means commercial equipment with little integration, or a large unit and a small lift. “High” means steam plus a large lift, a small unit, or full planning/integration on top of an equipment quote.

**Below 100 °C, hot water (single-stage, waste-heat source, roughly 1–5 MW)**

| | 2025 | 2030 | What it represents |
| --- | --- | --- | --- |
| Low | 400 €/kW_th | 350–400 €/kW_th | Near Hybrid Energy / Annex 58 low end and ACEEE economic MVC ($400/kW, US). Not a full new distribution loop. |
| Central | 700–900 €/kW_th | 650–850 €/kW_th | Older DEA traditional **0.73 M€/MW (2019 €)** and HACHP-minus-20%. Aligned in *level* with Rissman $700/kW_th (2021 USD) but **not** the same currency year. 2030 uses the older DEA learning step (0.87→0.78 by 2030 on HACHP), not a new 2026 traditional datasheet. |
| High | 1,200–1,500 €/kW_th | 1,100–1,400 €/kW_th | DEA 2026 *style* installed cost if integration or a two-stage layout is required even below 100 °C, or Pieper-like total project cost when the heat source is expensive. Swiss factor 2 on a ~700 €/kW machine lands here. |

**100–200 °C, hot water or steam (the user’s second bin). 200 °C machines are mostly large or still demonstration; DEA’s table stops at 150 °C plus an expectation of commercial 200 °C “within 3 years” of the 2026 text.**

| | 2025 | 2030 | What it represents |
| --- | --- | --- | --- |
| Low | 800 €/kW_th | 750 €/kW_th | Top of the Annex 58 commercial compression band (Siemens 250–800; Heaten ~250–450) **without** integration. Close to Rissman $870/kW_th (2021 USD) only after FX; do not treat 800 € as equal to $870. |
| Central | 1,400–1,600 €/kW_th hot water to 150 °C; **1,750 €/kW_th** if steam | 1,300–1,500 hot water; **1,650** steam | DEA 2026, 2025 € and 2030 € columns, up to 150 °C. This is the number to use if CAPEX must stand in for equipment plus installation. |
| High | 1,950–2,000 €/kW_th | ~1,850–1,950 €/kW_th if the 2025 adders are held flat | DEA worked example **1.95 M€/MW** (140 °C steam, 80 K lift, 2 MW, 2025). Zühlsdorf 2019 small-plant bottom-up **~1,870–2,000 €/kW** was for supply **above 150 °C** at ~8 MW (2019 costing). Olvondo-class and heat transformers (1,200–2,000 €/kW) sit in this high band even before integration. |

Suggested single baseline if the model keeps **one** number per temperature bin and wants installed EU cost in **2025 euros**: **900 €/kW_th below 100 °C** (high end of the older traditional-unit evidence, because the 2026 Excel for &lt;100 °C was not read) and **1,550 €/kW_th for 100–150 °C hot water**, switching to **1,750–1,950 €/kW_th** when the product is steam or the lift exceeds 75 K. Sensitivity then runs roughly **0.5× to 1.3×** on the hot-water central case (low equipment vs high steam/lift), which brackets Annex 58 through the DEA example.

For **2030**, the same DEA columns support holding the 2025 central case and applying about **−4% (hot water to 150 °C: 1.55→1.50)** to **−7% (steam to 125 °C: 1.40→1.30)**. A steeper decline is not what this catalogue now shows. The 2020 edition’s decline from 2020 to 2030 was larger (0.87→0.78, about −10%; 1.05→0.93, about −11%) and should not be stacked on top of the 2026 table.

**2021 USD and 2025 USD:** not computed here. To put DEA 2025 euros into 2021 dollars, apply a documented annual-average USD per EUR for 2025 and then a US CPI index from 2025 back to 2021 (or the reverse chain). Until that is done, do not replace $700 / $870 with a converted DEA figure. Order-of-magnitude only: 1,550 €/kW is well above $870/kW at any plausible 2020s exchange rate near 1.0–1.2 USD/EUR, so the gap is scope and vintage, not FX noise.

FOM to pair with these CAPEX values, if the model needs one and will not mix sources silently:

- Keep the user’s **$12 and $18 per kW_th-year (2021 USD)** with the user’s $700 / $870 CAPEX.
- If CAPEX is switched to DEA 2025 installed costs, a same-source FOM was **not** found. Scaling ACEEE’s 3% of CapEx would imply roughly **40–50 € per kW_th-year** on a 1,400–1,600 €/kW machine, which is a different O&M intensity than $12–18/kW-year. Do not apply 3% unless that maintenance definition is accepted.

### Gaps

- No audited FX or CPI series was applied, so a 2021-USD and 2025-USD table is intentionally absent.
- DEA 2030 figures are scenario judgements tied to IEA-style learning, not contracted 2030 prices.
- No 2025 traditional (&lt;100 °C) DEA number was extracted from the Excel, so the &lt;100 °C central band leans on the 2019/2020 catalogue.

## How do costs scale with temperature lift and capacity?

### Takeaway

Specific cost rises with temperature lift because a large lift forces a second stage or cascade; the Danish catalogue prices that as **about +0.2 M€/MW above 75 K** on top of the steam adder, and describes cascade **equipment** as almost **twice** single-stage. Specific cost falls with capacity in bottom-up and district-heating project data (roughly a factor of two from ~8 MW to ~50 MW above 150 °C; declining €/MW curves from 0.5 to 10 MW in Danish district heating). Supplier quote clouds in Annex 58 do **not** show a clean capacity slope, because size, refrigerant, and lift are mixed.

### Cited Findings

- DEA 2026: single-stage is the design target up to a process lift of about **50 K**. Above about **70 K**, cascades are typical and “increase initial capital expenditure”; “a cascade system is almost twice as expensive as a single stage system in terms of equipment cost.” Worked CAPEX adder for lift **above 75 K: 0.2 M€/MW**, separate from the **0.2 M€/MW** steam adder. Higher supply temperature band (150 °C vs 125 °C) is **1.55 vs 1.20 M€/MW** in 2025 (hot water), i.e. +0.35 M€/MW. Steam vs hot water at the same cap is +0.20 M€/MW in that table (1.40 vs 1.20; 1.75 vs 1.55). COP example at 80 K lift: 2.4 hot water, then −15 percentage points for steam → 2.25. Large machines (≥5 MW, and 7–70 MW) are where supply temperatures toward **200 °C** are offered; ~1 MW commercial units were described as limited to about **150 °C**, with a broader 200 °C roll-out hoped for within about three years. — [DEA PDF](https://ens.dk/media/7757/download)
- Annex 58: “general trend with **higher cost for higher temperature lift**” across 20–190 °C mean lift and 200–1,200 €/kW (ex integration). “Minor trend” of lower cost at lower maximum supply temperature; **steam compression is the exception**. “**No clear trend**” of specific cost versus capacity in the supplier sample (0.03–70 MW). Separately, maximum achievable supply temperature tends to be higher at larger capacity. — [Annex 58 PDF](https://heatpumpingtechnologies.org/annex58/wp-content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf)
- Zühlsdorf et al. 2019: specific TCI about **950 €/kW at ~50 MW** versus about **1,900 €/kW at ~8 MW**, same COP class (~1.6–1.9), supply above 150 °C. Authors’ conclusion: economy of scale lowers specific investment as capacity rises. — [PDF](https://backend.orbit.dtu.dk/ws/files/195360755/Analysis_of_technologies_and_potentials_for_heat_pump_based.pdf)
- Pieper / Annex 48 (district heating, total project, not factory process heat): specific cost declines with MW. Excess heat: 1.30–0.97 M€/MW below 1 MW, 0.97–0.72 between 1 and 4 MW, 0.72–0.67 between 4 and 10 MW. Other sources (sewage, groundwater, air) show the same shape at a higher level. A later cost-function paper writes power-law fits on those data, for example groundwater investment ≈ 1.11·Q^(−0.23) to 1.24·Q^(−0.26) in M€/MW (Q in MW); those exponents are fits to **district-heating projects**, not to industrial steam heat pumps. — [Annex 48 PDF](https://backend.orbit.dtu.dk/ws/files/220010789/Denmark_2019_2.pdf); [Meesenburg et al. PDF](https://backend.orbit.dtu.dk/ws/portalfiles/portal/162448930/ISEC_Feasibility_of_heat_pumps_supplying_DH_systems_WMeesenburg_Final.pdf)
- DEA general guideline (all technologies, not a heat-pump regression): economy-of-scale correction uses a proportionality factor “usually about **0.6–0.7** for power plants,” applied only inside the stated typical size range, and only for plants that differ mainly by size. Stated example range for an older HACHP entry: **0.5–5 MW**, typical **2 MW**. — [DEA PDF](https://ens.dk/media/7757/download)
- ACEEE: technical (higher lift, extra stage) capital is **2×** economic for MVC ($800 vs $400 per kW_th) and for MVR. The economic case capped lift near **40 K**. — [ACEEE PDF](https://www.aceee.org/sites/default/files/pdfs/ie2201.pdf)
- Kalina et al. 2024, sewage-source heat pump for district heating (Poland): market range cited as **250–800 €/kW_th** installed without integration, depending on capacity, lift, and scope; “expected value for 10 MW_th” **350–500 €/kW_th**. Their own total CAPEX is site-specific and adds transformer, 1.5 km cable, tanks, building, and a PV plant, so it is not a heat-pump-only cost. — [journal PDF](https://www.journals.pan.pl/Content/133115/10_AoT_4-2024_Kalina_713.pdf?handler=pdf)

### Inferences

- For a sensitivity knob, two additive European adjustments are directly sourced: **+200 €/kW** if the sink is steam rather than hot water (DEA 2026 table difference), and **+200 €/kW** if lift exceeds 75 K (worked example). Together they take 1,550 €/kW to 1,950 €/kW. A cruder alternative is to **double equipment cost** when moving from one stage to a cascade (DEA text and ACEEE’s 2× technical case).
- Capacity: inside 1–10 MW, project data support a mild decline (Pieper: excess-heat total cost ~0.97 to ~0.67 M€/MW from the 1 MW class to the 4–10 MW class). The sharp drop (~2×) in Zühlsdorf 2019 is between ~8 and ~50 MW and is for >150 °C cycles. Below ~1 MW, both Pieper and the Swiss ~0.5–0.6 MW quotes (840–1,300 €/kW before integration) point to higher specific cost. Do not apply the power-plant 0.6–0.7 exponent unless the model documents it as a generic scale factor; it is not a heat-pump fit.
- Heat-source quality changes **project** cost more than compressor cost in the Danish district-heating sample (groundwater high, flue gas or on-site excess heat low). An industrial site that already has a clean liquid waste-heat stream should not inherit groundwater-well costs.

### Gaps

- No continuous cost-versus-lift curve (for example €/kW per 10 K) was published in the sources read. DEA gives a step at 75 K, not a slope.
- Annex 58’s lift and capacity charts are described in text; the underlying plot values were not digitized.
- Scaling above 150 °C toward 200 °C is discussed qualitatively (DEA: commercial at large MW, not yet at ~1 MW) without a 200 °C €/kW row.
