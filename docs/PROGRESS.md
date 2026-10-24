# Carbon Gap: build progress and handoff

Living document, updated after every phase so any engineer or coding agent (Claude Code, Codex…) can pick up the work. Read this first, then `PRODUCT.md`.

Event: OpenAI Paris DevDay Community Hackathon, 24–25 October 2026 (online). Submission before Sunday 25 Oct, midnight Paris time: 2-minute pitch video (required), project link + GitHub repo (optional). Finale 26 Oct at Hexa. Tracks: Impact (climate action) + Build in public (tag @borvibe and @openaidevs, #parisdevdayhack). Judged partly on how well the OpenAI API is used.

Repo: github.com/ISMMO0/carbon-gap (private).

## 1. The product in one paragraph

Carbon Gap compares what countries and companies **declare** they emit with what independent data **observes** (satellite + asset-level estimates), shows the gap on an interactive globe, and values it at the carbon price. An AI analyst (OpenAI, function calling) answers questions and drives the map, and writes sourced reports. Framing: "gap to investigate", never "fraud".

## 2. Where things are

```
PRODUCT.md            product context (users, purpose, principles)
mockup/index.html     clickable mockup, single file, SYNTHETIC data, no backend needed
backend/app/main.py   FastAPI: /api/health + serves the mockup at /
backend/.env          keys (git-ignored). Template: backend/.env.example
docs/PROGRESS.md      this file
```

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

## 5. Next

- Real data pipeline (national inventories, EU ETS, Climate TRACE, Sentinel-5P, grid data) → prepared local files.
- Replace the scripted analyst with OpenAI Responses API + function calling; same tool names as the mockup.
- Structured Outputs to extract declared emissions from company reports (PDF).
- Report generation by the model, Realtime voice (bonus), deploy.
