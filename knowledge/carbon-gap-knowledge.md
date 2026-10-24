# Carbon Gap knowledge base

Reference notes for the Carbon Gap analyst: how emissions are reported, how independent estimates differ, carbon markets and taxes, and national targets.
Status: compiled for the OpenAI Paris DevDay hackathon (October 2026) from public knowledge up to mid-2026. Policies change: when a fact matters for publication, confirm it with a current source (web search) and cite that source.

---

## 1. How countries report emissions (the "declared" side)

### UNFCCC national inventories
- Parties to the UN Framework Convention on Climate Change (UNFCCC) report national greenhouse-gas (GHG) inventories built with IPCC methodologies (mainly the 2006 IPCC Guidelines and the 2019 Refinement).
- **Annex I countries** (OECD members in 1992 plus economies in transition, e.g. EU members, US, UK, Japan, Canada, Australia, Russia, Ukraine, Türkiye, Kazakhstan, Belarus, New Zealand) submit a full inventory **every year**, around 15 April, covering the year X-2 (submission 2025 covers 2023). The data tables were called the Common Reporting Format (CRF), replaced by the Common Reporting Tables (CRT) under the Paris Agreement.
- **Non-Annex I countries** (all other countries, including China, India, Brazil, Indonesia, Saudi Arabia, Iran, South Africa, Mexico) historically reported far less often, through **National Communications (NCs)** and **Biennial Update Reports (BURs)**. Many inventories in these reports are several years old.
- Inventories cover CO2, CH4, N2O and fluorinated gases (HFCs, PFCs, SF6, NF3), grouped in sectors: **Energy** (fuel combustion, fugitive emissions from fuels, transport), **Industrial Processes and Product Use (IPPU)**, **Agriculture**, **LULUCF** (land use, land-use change and forestry) and **Waste**.
- Totals are reported **with and without LULUCF**. Carbon Gap compares totals **without LULUCF**, because forest sinks are highly uncertain and modelled differently by independent estimates.

### The Paris Agreement Enhanced Transparency Framework (ETF)
- Since the Paris Agreement, all Parties report under common rules (Modalities, Procedures and Guidelines, decision 18/CMA.1).
- The first **Biennial Transparency Reports (BTRs)** were due by **31 December 2024**. Each BTR contains a national inventory report, progress on the NDC, and support needed/received. Developing countries have some flexibility (e.g. older latest year, fewer gases) if they explain why.
- Many large non-Annex I emitters submitted their first BTR around the end of 2024 and early 2025. Example: **China's first BTR** (published 3 January 2025) reports total GHG emissions excluding LULUCF of about **14.3 GtCO2e for 2021**. India, Brazil, Indonesia, South Africa and others also published BTRs or updated inventories in 2024–2025; check the UNFCCC "BTR" submissions page for the latest year and figure.
- Under the ETF, inventories use **100-year Global Warming Potentials from the IPCC Fifth Assessment Report (AR5)**: CH4 = 28 (non-fossil), N2O = 265. Older reports often used AR4 values (CH4 = 25, N2O = 298) or SAR values (CH4 = 21). Changing GWPs alone changes a methane-heavy country's total by several percent.

### Why declared figures can be low or late
- Emission factors are often **default IPCC Tier 1 values** rather than measured values.
- **Fugitive methane** from oil, gas and coal (leaks, venting, flaring, coal mine methane) is hard to estimate and is often underestimated in inventories.
- Activity data (fuel use, livestock numbers, waste volumes) may be incomplete, especially in the informal sector.
- Reporting lag: annual for Annex I (2 years behind), irregular for many others (5–10 years behind before the BTRs).
- Scope choices: international aviation and shipping are reported as memo items, not in national totals.

---

## 2. Independent estimates (the "observed" side)

### Climate TRACE
- A coalition (founded 2020, including WattTime, TransitionZero, RMI and others, co-convened with Al Gore) that estimates emissions for every country and hundreds of thousands of individual sources (power plants, steel and cement plants, oil and gas fields, refineries, mines, ships, farms, landfills) using satellite imagery, remote sensing, machine learning and public activity data.
- Coverage: all countries, most sectors, annual and monthly data, asset-level estimates with confidence ratings. Free API (api.climatetrace.org).
- Known sources of divergence with inventories:
  - **Fossil fuel operations**: Climate TRACE's oil, gas and coal methane estimates are often much higher than inventories. This drives large gaps for producers such as Russia, Australia, Kuwait, Kazakhstan, Turkmenistan, Algeria.
  - **Agriculture and waste**: modelled from livestock, rice, fertiliser and landfill data; can be higher or lower than inventories.
  - **Manufacturing and buildings**: modelled partly from energy balances; boundary differences with inventory categories.
  - Climate TRACE uses its own GWP choices (100-year values reported as co2e_100yr) that may differ from a country's inventory.
- Treat a gap as a **lead to investigate**, with the sector breakdown pointing to where the difference comes from.

### Other independent sources
- **IEA Global Methane Tracker**: estimates energy-sector methane far above official reports; the IEA has repeatedly found real energy methane emissions to be substantially higher (on the order of 70–80 % globally) than what countries report.
- **EDGAR** (European Commission Joint Research Centre): consistent global emissions database by country and sector, based on activity data and emission factors (not satellites).
- **Global Carbon Project / Global Carbon Budget**: annual fossil CO2 estimates by country.
- **Satellites**: Sentinel-5P/TROPOMI (methane, NO2), GHGSat, MethaneSAT (launched 2024, lost contact in 2025), Carbon Mapper / Tanager-1 (2024) detect methane super-emitters; OCO-2/OCO-3 measure CO2 columns. The EU Copernicus CO2M mission is planned to monitor anthropogenic CO2.
- **UNEP International Methane Emissions Observatory (IMEO)** and its Methane Alert and Response System (MARS) notify governments and companies about large plumes detected by satellite.

---

## 3. Carbon pricing: markets and taxes

### Concepts
- **Emissions trading system (ETS, cap-and-trade)**: a cap on total emissions from covered installations; allowances (1 allowance = 1 tCO2e) are allocated for free or auctioned and can be traded. Installations must surrender allowances equal to their verified emissions each year. Installations with a **surplus** (allocation above emissions) can sell; those with a **shortfall** must buy.
- **Carbon tax**: a fixed price per tonne on fuels or emissions.
- **Offsets / credits**: certified reductions or removals from projects outside the capped sectors (compliance or voluntary markets).
- **Intensity-based ETS**: allocation tied to output (tCO2 per MWh or per tonne of product) instead of an absolute cap (e.g. China, India).

### European Union
- **EU ETS** (since 2005): power and heat, energy-intensive industry (steel, cement, refining, chemicals, aluminium, paper, glass), intra-EEA aviation, and **maritime transport since 2024**. Covers roughly 40 % of EU emissions.
- Emissions are **verified per installation** every year; verified emissions and free allocation per installation are public in the **EU Transaction Log / Union Registry** (and EEA datasets). This is the best public source for site-level declared emissions in Europe.
- The cap falls every year (linear reduction factor 4.3 % per year 2024–2027, 4.4 % from 2028). Target: −62 % ETS emissions by 2030 vs 2005. A Market Stability Reserve removes surplus allowances.
- Allowance (EUA) prices: roughly €60–100 per tonne over 2022–2025 (peak near €100 in early 2023). Carbon Gap uses **€72/t as an assumption**, not a live price.
- **ETS2** covers fuels for buildings and road transport, scheduled to start in 2027; EU institutions have discussed postponing it to 2028. Check the current status.
- **CBAM** (Carbon Border Adjustment Mechanism): transitional reporting phase October 2023–end 2025; definitive phase from **1 January 2026**, when importers of cement, iron and steel, aluminium, fertilisers, electricity and hydrogen must buy CBAM certificates priced on the EU ETS. Free allocation for these sectors is phased out from 2026 to 2034.
- EU climate law: **−55 % net GHG by 2030 vs 1990**, climate neutrality by 2050; a **2040 target of −90 %** (with a limited share of international credits) was agreed in 2025.
- **EU Methane Regulation** (2024): measurement, reporting and verification (MRV), leak detection and repair, and bans on routine venting/flaring for EU oil, gas and coal; progressively applies equivalent MRV requirements to imported fossil fuels (around 2027–2030).

### Other systems
- **United Kingdom**: UK ETS since 2021 (after leaving the EU ETS); plans to link with the EU ETS were announced in 2025. UK CBAM planned from 2027. Targets: −68 % by 2030 and −81 % by 2035 vs 1990, net zero 2050 (legally binding, Climate Change Act).
- **Switzerland**: ETS linked to the EU ETS since 2020; CO2 levy on heating fuels.
- **China**: national ETS launched in 2021 for the power sector (over 2,000 plants, about 4.5–5 GtCO2), intensity-based. Expanded in 2025 to **steel, cement and aluminium**. A voluntary offset market (CCER) relaunched in 2024. Targets: peak CO2 before 2030, carbon neutrality before 2060; 2035 NDC (September 2025): cut economy-wide net GHG emissions by 7–10 % from peak levels.
- **South Korea**: K-ETS since 2015, covering most of national emissions. NDC: −40 % by 2030 vs 2018; carbon neutrality 2050.
- **Japan**: GX League voluntary ETS from 2023; a mandatory GX-ETS for large emitters (around 100 ktCO2/year and more) starts in fiscal year 2026; carbon levy on fossil fuel importers from 2028. Targets: −46 % by 2030, −60 % by 2035, −73 % by 2040 vs 2013; net zero 2050.
- **India**: Carbon Credit Trading Scheme (CCTS) created in 2023, with emission-intensity targets for energy-intensive sectors notified from 2025. NDC: −45 % emissions intensity of GDP by 2030 vs 2005, 50 % non-fossil power capacity by 2030; net zero 2070.
- **Indonesia**: intensity-based ETS for coal power plants since 2023, carbon exchange (IDXCarbon) since 2023. Net zero 2060.
- **Brazil**: law creating a regulated carbon market (SBCE) adopted in December 2024, phased implementation over several years. NDC 2035: −59 % to −67 % vs 2005. Hosted COP30 in Belém (November 2025).
- **United States**: no federal carbon price. State systems: **California** cap-and-trade (since 2013, linked with Québec), extended in 2025 as "cap-and-invest" to 2045; **RGGI** (power sector, north-eastern states); **Washington** cap-and-invest (2023). The US submitted a 2035 NDC (−61 to −66 % vs 2005) in December 2024, then the administration ordered withdrawal from the Paris Agreement in January 2025 (effective one year later). The federal methane fee on oil and gas was repealed in 2025.
- **Canada**: consumer fuel charge set to zero from April 2025; industrial output-based pricing systems remain. Targets: −40 to −45 % by 2030, −45 to −50 % by 2035 vs 2005; net zero 2050.
- **Australia**: Safeguard Mechanism (reformed 2023) sets declining baselines for facilities above 100 ktCO2e/year, with tradable Safeguard Mechanism Credits. Targets: −43 % by 2030 vs 2005, 2035 target of −62 to −70 % (announced 2025); net zero 2050.
- **New Zealand**: NZ ETS since 2008, covers forestry and most sectors except biogenic agricultural methane.
- **Sweden**: carbon tax since 1991, among the highest in the world (around €100–130 per tonne).
- **Russia**: no national carbon price; Sakhalin regional experiment. Target: 2030 emissions at 70 % of 1990 levels (including large forest sink assumptions); carbon neutrality 2060.
- **Saudi Arabia**: net zero 2060 target; no carbon price. **Iran**: has signed but not ratified the Paris Agreement.
- **Kazakhstan**: national ETS since 2013 (relaunched 2018). **Mexico**: pilot ETS since 2020 and a federal carbon tax on fuels.
- **South Africa**: carbon tax since 2019 (with large allowances lowering the effective rate).

### International markets
- **Paris Agreement Article 6**: Article 6.2 allows bilateral transfers of mitigation outcomes between countries (ITMOs) with "corresponding adjustments" to avoid double counting (e.g. Switzerland, Singapore, Japan buying from Ghana, Peru, Thailand and others). Article 6.4 creates the **Paris Agreement Crediting Mechanism** (successor to the Clean Development Mechanism); its rules were finalised at COP29 in Baku (November 2024).
- **CORSIA**: ICAO scheme requiring airlines to offset international aviation emissions growth; first mandatory phase 2024–2026.
- **Voluntary carbon market**: corporate offsetting; integrity frameworks from the ICVCM (Core Carbon Principles) and VCMI.

### Methane commitments
- **Global Methane Pledge** (COP26, 2021): over 150 countries aim to cut global methane emissions by 30 % by 2030 vs 2020. China, India and Russia have not joined.
- **Oil and Gas Decarbonization Charter** (COP28, 2023): producing companies pledged near-zero upstream methane by 2030 and an end to routine flaring.

---

## 4. Reading a gap: checklist for the analyst

1. **Same year?** Compare the inventory year with the observed year. Carbon Gap always compares the same year.
2. **Same scope?** Totals exclude LULUCF on both sides. Check whether international bunkers or specific gases are excluded.
3. **Which sector drives the gap?** Energy & industry gaps in fossil fuel producers usually come from **fugitive methane**; agriculture gaps from livestock and rice models; waste gaps from landfill methane.
4. **GWP version**: AR4 vs AR5 vs AR6 values can move totals by a few percent for methane-heavy countries.
5. **Confidence**: Climate TRACE asset confidence (very low to very high) and the inventory tier used.
6. **Corroboration**: look for satellite plume detections (IMEO/MARS, Carbon Mapper), IEA Methane Tracker estimates, investigative reporting, company disclosures, EU ETS verified emissions for European sites.
7. **Framing**: say "gap to investigate", never "fraud" or "lie". Inventories follow agreed rules; independent estimates have their own uncertainty.

### Money: what a gap is worth
- Gap value = gap (tCO2e) × carbon price. At €72/t, 1 MtCO2e is worth €72 million.
- In a cap-and-trade system, under-reported emissions at covered installations mean allowances that should have been surrendered were not: a direct market distortion.
- For countries, unreported emissions affect NDC progress claims, Article 6 transfers (a country selling ITMOs with under-reported emissions inflates the credits) and CBAM default values.

---

## 5. Glossary
- **CO2e (CO2-equivalent)**: emissions of all gases converted to CO2 using GWP values.
- **GWP100 / GWP20**: warming over 100 / 20 years relative to CO2. Methane is ~28–30 times CO2 over 100 years and ~80 times over 20 years.
- **NDC**: Nationally Determined Contribution, a country's climate pledge under the Paris Agreement, updated every five years (new round with 2035 targets due in 2025).
- **BTR**: Biennial Transparency Report (Paris Agreement, from December 2024).
- **BUR / NC**: Biennial Update Report / National Communication (older non-Annex I reports).
- **CRF / CRT**: Common Reporting Format / Common Reporting Tables (inventory data tables).
- **MRV**: Measurement, Reporting and Verification.
- **Fugitive emissions**: unintended releases (leaks) and venting/flaring from fossil fuel production and transport.
- **Free allocation**: allowances given for free to installations at risk of carbon leakage.
- **Carbon leakage**: production moving to countries with weaker climate policy.
- **Super-emitter**: a single source releasing very large amounts of methane, often detectable by satellite.
