# Carbon Gap

**What countries and companies declare they emit vs. what independent data observes, valued at the price of carbon.**

Greenhouse-gas emissions drive global warming, ocean acidification, habitat loss and public-health damage. Carbon already has a price (EU ETS, carbon taxes, CSRD reporting), yet emissions are mostly self-declared, computed from averages and emission factors, and published months or years late.

Carbon Gap puts official declarations next to independent estimates on an interactive globe, and lets an AI analyst explain the gaps, drive the map, research missing data and write sourced reports. You can talk to it.

Built for the **OpenAI Paris DevDay Community Hackathon** (24–25 October 2026). Tracks: Impact (climate action) and Build in public.

## What it does

- **Emissions gap**: for 77 countries, the total declared to the UN (UNFCCC inventories, or recent Biennial Transparency Reports found by research agents) vs Climate TRACE estimates for the same year, by sector, with the largest emitting sites on the map.
- **Companies**: the 40 largest emitting groups, their tracked sites (Climate TRACE) vs the Scope 1 they report themselves.
- **Carbon market**: EU ETS free allowances vs verified emissions per country and sector: who must buy, who has a surplus.
- **Analyst**: ask anything; it reads the data, moves the globe, searches the web and a curated knowledge base, and cites its sources.
- **Research agents**: run in parallel to find missing declarations in official reports; every figure must come with a verbatim quote found in its source, and can be verified by a person.
- **Reports**: one-click dossiers with findings, sites to investigate and next steps, plus a spoken briefing.
- **Voice**: talk to Carbon Gap; it answers out loud while the map moves.

A gap is a lead to investigate, never proof of misreporting.

## OpenAI in Carbon Gap

| Feature | OpenAI API |
|---|---|
| Analyst (map tools, data tools, agents as tools) | Responses API, `gpt-5.5`, function calling, streaming |
| Recent context | built-in `web_search` with citations |
| Knowledge base (reporting rules, carbon markets, national targets) | `file_search` over a vector store |
| Research agents (countries and companies) | Structured Outputs (strict JSON schema) |
| Grouping subsidiaries under parent companies | Structured Outputs |
| Dossiers | Structured Outputs + `web_search` |
| Spoken report briefing | `gpt-4o-mini-tts` |
| Voice input | `gpt-4o-transcribe` |

Also used: ElevenLabs (spoken answers in voice mode), Keenable (web search and page reading for research agents), Postgres on Aiven (research findings).

## Data

- Declared: UNFCCC national inventories via the [Climate Watch API](https://www.climatewatchdata.org/), Biennial Transparency Reports and national reports found by research agents.
- Observed: [Climate TRACE](https://climatetrace.org/) country and asset-level estimates (API v6).
- Carbon market: EEA EU ETS Union Registry data, via [datahub.io](https://github.com/datasets/eu-emissions-trading-system).
- Carbon price: €72/t, an assumption, not a live price.

## Run locally

```bash
cd backend
uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY (+ ELEVENLABS_API_KEY, KEENABLE_API_KEY, DATABASE_URL)
.venv/bin/uvicorn app.main:app --port 8010
```

Open http://localhost:8010. Rebuild data with the scripts in `backend/scripts/` (see `docs/PROGRESS.md`).
