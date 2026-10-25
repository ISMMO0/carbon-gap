# Carbon Gap: build progress and handoff

Living document, updated after every phase so any engineer or coding agent (Claude Code, Codex…) can pick up the work. Read this first, then `PRODUCT.md`.

Event: OpenAI Paris DevDay Community Hackathon, 24–25 October 2026 (online). Submission before Sunday 25 Oct, midnight Paris time: 2-minute pitch video (required), project link + GitHub repo (optional). Finale 26 Oct at Hexa. Tracks: Impact (climate action) + Build in public (tag @borvibe and @openaidevs, #parisdevdayhack). Judged partly on how well the OpenAI API is used.

Repo: github.com/ISMMO0/carbon-gap (private).

## 1. The product in one paragraph

Carbon Gap compares what countries and companies **declare** they emit with what independent data **observes** (satellite + asset-level estimates), shows the gap on an interactive globe, and values it at the carbon price. An AI analyst (OpenAI, function calling) answers questions and drives the map, and writes sourced reports. Framing: "gap to investigate", never "fraud".

## 2. Where things are

```
PRODUCT.md                    product context (users, purpose, principles)
web/                          the real app (index.html, style.css, app.js), served at /
mockup/index.html             original clickable mockup, SYNTHETIC data, served at /mockup
backend/app/main.py           FastAPI routes + static hosting
backend/app/data.py           declared vs observed data, site fetch (Climate TRACE, disk cache)
backend/app/agent.py          analyst: Responses API, gpt-5.5, function calling + web_search, SSE events
backend/app/report.py         dossiers: Structured Outputs + web_search; spoken briefing (gpt-4o-mini-tts)
backend/app/research.py       research agents: Keenable search/fetch + gpt-5.5 Structured Outputs, quote-checked
backend/app/store.py          findings in Postgres (DATABASE_URL, Aiven), local JSON fallback if unreachable
backend/scripts/build_data.py builds backend/data/countries.json from the live APIs
backend/scripts/research_batch.py / research_retry.py   run research agents in parallel
backend/scripts/sync_knowledge.py   uploads knowledge/*.md to an OpenAI vector store (file_search)
knowledge/carbon-gap-knowledge.md   reporting rules, carbon markets & taxes, national targets, how to read a gap
backend/.env                  keys (git-ignored). Template: backend/.env.example
video/                        motion film pipeline (director.js, record.py, audio.py)
```

API: `GET /api/countries`, `GET /api/countries/{iso3}/sites`, `POST /api/chat` (SSE: delta, tool, action, sources, done, error),
`POST /api/report/{iso3}` (cached in data/reports), `GET /api/report/{iso3}/audio`.

## 3. How to run

```
cd backend
uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt   # once
.venv/bin/uvicorn app.main:app --port 8010 --reload                                      # http://localhost:8010
```
Or open `mockup/index.html` directly in a browser.

## 4. Phase log

### Phase 0: repo + mockup ✅
- Private repo, README, PRODUCT.md.
- Mockup (all fake data): orthographic globe coloured by gap (hatched = low confidence), metric switch (gap / declared / observed), sector filters, year; country sheet with declared-vs-observed "strata" chart, sector breakdown, sortable site table, sources; scripted analyst that calls map "tools" (highlight_countries, fly_to, set_layer, select_country, focus_site, generate_report); report view with print-to-PDF.
- Design direction: geological survey map (light paper, flat tints, hatching, Barlow).

### Phase 1: real app ✅ (24 Oct evening)
- Data: declared = UNFCCC inventories via Climate Watch API (Annex I + non-Annex I, total excl. LULUCF, latest year ≥ 2015);
  observed = Climate TRACE v6 for the SAME year, all sectors except forestry. 64 countries compared, 172 observed-only
  (no UN inventory since 2015: China, Indonesia, Iran, Saudi Arabia…). Sector groups: energy & industry (Energy + IPPU),
  agriculture, waste. Rebuild: `cd backend && .venv/bin/python -m scripts.build_data` (~25 s).
- Sites: Climate TRACE assets (2024) for power, manufacturing, fossil fuel ops, mining, waste; top 60 by emissions, cached.
- Analyst: gpt-5.5 (reasoning low), tools get_country / rank_countries / get_sites + map tools select_country /
  highlight_countries / focus_site / set_metric / open_report (forwarded to the browser) + built-in web_search with
  citations. Conversation kept with previous_response_id. ~8 s per answer.
- Reports: gpt-5.5 + web_search + strict JSON schema (headline, summary, findings, sectors, sites, next steps, caveats,
  briefing). ~30 s, cached. Briefing read by gpt-4o-mini-tts (voice sage).
- Tested in the browser: map, country sheets, sites, chat (ranking, Poland sites, France vs Germany + web news), report, audio.
- Known caveats: carbon price €72/t is an assumption; GWP versions differ (inventories AR4/AR5, Climate TRACE 100-yr);
  Climate TRACE methane estimates drive many large gaps.

### Phase 2: research agents, knowledge base, Postgres ✅ (24 Oct night)
- Knowledge base (knowledge/carbon-gap-knowledge.md) in an OpenAI vector store; the analyst uses file_search for
  markets, laws, targets, methodology, and web_search for recent news.
- Research agents fill countries with no UN inventory in Climate Watch: 2 Keenable searches → read 3 best pages →
  gpt-5.5 extracts total excl. LULUCF with strict schema → the quote must be found verbatim in the cited source
  (else rejected) → Climate TRACE fetched for the same year → saved. Run in parallel (asyncio, semaphore);
  Keenable rate-limits bursts, so search retries with backoff and concurrency 3 is safe.
- Results: 13 found (China 14,314 Mt 2021 BTR1, Indonesia, Mexico, South Africa, Saudi Arabia, Iraq, UAE, Algeria,
  Thailand, Vietnam, Malaysia, Taiwan, Philippines), not found: Iran, Egypt, Nigeria, Qatar, Argentina.
  All shown as "found by research agent · unverified" with quote + source link. 77 countries compared in total.
- Live: "Find its latest declaration" button in country sheets (SSE steps), and the analyst tool research_declaration.
- Postgres (Aiven) table `findings`, created on startup; /api/health shows which store is used.
- TODO: human verification flow (verified flag exists), Algeria's source is a LinkedIn post (medium confidence).

### Phase 3: voice, carbon market, verification ✅ (24 Oct night)
- Voice mode ("Talk" in the top bar, web/voice.js): mic → /api/transcribe (gpt-4o-transcribe) → analyst in voice mode
  (2 spoken sentences, still moves the map) → /api/speak (ElevenLabs flash v2.5, voice Sarah, streamed into <audio>)
  → listens again. Silence detection ends a turn; tap the orb (or Space) to send / interrupt; Esc closes.
  The orb is drawn on canvas: contour rings driven by mic / speaker level. Tested end to end in headless Chrome
  with a fake microphone (Playwright, --use-file-for-fake-audio-capture). The Browser pane blocks the mic.
- Carbon market tab: EU ETS verified emissions vs free allowances per country and sector (2025), history since 2013,
  shortfall valued at €72/t. Data: datahub.io EU ETS package of the EEA Union Registry (scripts/build_market.py,
  raw CSV in data/raw, git-ignored). Analyst tools get_market + show_market.
- Human verification: "I checked the source" on agent findings → POST /api/research/{iso3}/verify (Postgres).

### Phase 4: companies, logo ✅ (25 Oct, early)
- scripts/build_companies.py: Climate TRACE assets (power, manufacturing, fossil fuel ops, mining; 24 countries; 2023-24),
  emissions split equally between co-owners, subsidiaries grouped under parents by gpt-5.5 (Structured Outputs) → top 40.
- Company research agents (research.research_company): self-reported Scope 1 from reports, quote check, plus a
  plausibility check (rejected if far below the company's own tracked sites: unit errors). 14 found.
  Story: Coal India reports 26.7 Mt Scope 1, its tracked mines emit 66 Mt (coal mine methane).
- Companies tab, analyst tools get_companies / show_company / research_company. Table company_findings in Postgres.
- New logo (web/logo.svg): globe crossed by declared/observed bands, the gap hatched. Also the favicon.

### Phase 5: any company, simpler UI ✅ (25 Oct)
- backend/app/discover.py: research ANY company. gpt-5.5 + web_search + Structured Outputs profile (subsidiaries,
  countries with large facilities, sectors) → Climate TRACE assets in those countries matched on owner names →
  company research agent for reported Scope 1. ~20-60 s. Saved in Postgres table company_profiles.
  Entry points: search bar (unknown names), "Research any company" box in Companies, analyst tool discover_company,
  scripts/discover_companies.py (30 well-known groups pre-run). Now 72 companies, 44 with a reported Scope 1.
- UI: left rail removed (metric switch, symbols and "How we compare" live in the legend), unified search for countries
  and companies, hero with the headline number (6.2 Gt more than declared, about the US), 60-second guided tour
  (China, Coal India, Polish allowances, voice), analyst collapsed by default, front-end served with no-cache.

### Phase 6: satellite, swarm, share ✅ (25 Oct afternoon)
- Satellite view of any site (Esri World Imagery tiles at zoom 15, credited), opened by clicking a site or by the
  analyst's focus_site. E.g. Bełchatów's cooling towers.
- Agent swarm: POST /api/swarm runs N country agents in parallel (research.swarm merges their events into one SSE
  stream). Globe shows pulsing rings per agent, a live panel lists their steps, countries recolour as declarations
  are found. Button in the World sheet, analyst tool launch_agents. 81 countries compared now.
- Share card: 1200×675 PNG of a country or company finding (canvas), for X posts.

## 5. Next

- Structured Outputs to extract declared emissions from company reports (PDF) → company-level gaps.
- Deploy, re-shoot the film with real data, pitch video.
