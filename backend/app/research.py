"""Research agents: find the latest official GHG inventory a country reported to the UN
(BTR, national inventory report, BUR, national communication) when our dataset has none since 2015.

Search and page reading: Keenable. Understanding and extraction: OpenAI (Structured Outputs).
Every figure must come with a source URL and a verbatim quote found in that source."""
import asyncio
import json
import os
import re
from collections.abc import AsyncIterator

import httpx
from openai import AsyncOpenAI

from . import data, store

KEENABLE = "https://api.keenable.ai/v1"
EXTRACT_MODEL = "gpt-5.5"
PAGE_CHARS = 14000
MIN_YEAR = 2015

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["found", "year", "total_mt", "energy_mt", "agriculture_mt", "waste_mt", "document",
                 "source_url", "quote", "confidence", "notes"],
    "properties": {
        "found": {"type": "boolean", "description": "True only if a national total excluding LULUCF is stated in the sources."},
        "year": {"type": ["integer", "null"], "description": "Inventory year the total refers to (not the publication year)."},
        "total_mt": {"type": ["number", "null"], "description": "Total GHG emissions EXCLUDING LULUCF, in MtCO2e."},
        "energy_mt": {"type": ["number", "null"], "description": "Energy + industrial processes (IPPU), MtCO2e, if stated."},
        "agriculture_mt": {"type": ["number", "null"]},
        "waste_mt": {"type": ["number", "null"]},
        "document": {"type": "string", "description": "Name of the official report, e.g. 'First Biennial Transparency Report (2024)'."},
        "source_url": {"type": "string", "description": "URL of the source that states the total. Must be one of the provided URLs."},
        "quote": {"type": "string", "description": "Short verbatim sentence copied from that source that contains the total."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"],
                       "description": "high = official document or UNFCCC page; medium = reputable outlet citing it; low = unclear."},
        "notes": {"type": "string", "description": "Caveats: GWP version, whether LULUCF excluded, unit conversions done."},
    },
}

PROMPT = """You are a climate data researcher. Find the most recent national greenhouse-gas inventory total that {name}
officially reported to the UNFCCC (Biennial Transparency Report, National Inventory Report, Biennial Update Report or
National Communication), for an inventory year of {min_year} or later.

Rules:
- Use only the sources below. Never use your own memory for numbers.
- The total must EXCLUDE LULUCF (land use and forestry). If only the total including LULUCF is given, set found=false
  unless both are stated.
- Convert units to MtCO2e (1 GtCO2e = 1000 MtCO2e; 1 GgCO2e = 0.001 MtCO2e; kt = Gg).
- source_url must be one of the URLs below, and quote must be copied word for word from that source.
- Prefer the official document or unfccc.int over news, and the latest inventory year.

SOURCES:
{sources}"""


def _headers():
    return {"X-API-Key": os.environ["KEENABLE_API_KEY"]}


async def _search(http: httpx.AsyncClient, q: str) -> list[dict]:
    """Keenable search, retried with backoff (it rate-limits bursts of parallel agents)."""
    for attempt in range(4):
        try:
            r = await http.post(f"{KEENABLE}/search", json={"query": q, "mode": "realtime"}, headers=_headers())
            if r.status_code == 200:
                return r.json().get("results") or []
        except httpx.HTTPError:
            pass
        await asyncio.sleep(2 * 2 ** attempt)
    raise RuntimeError("search unavailable")


async def _fetch(http: httpx.AsyncClient, url: str) -> str:
    try:
        r = await http.get(f"{KEENABLE}/fetch", params={"url": url, "live": "true"}, headers=_headers(), timeout=25)
        return (r.json().get("content") or "")[:PAGE_CHARS] if r.status_code == 200 else ""
    except Exception:
        return ""


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s or "").lower().strip()


async def _observed(http: httpx.AsyncClient, iso3: str, year: int) -> dict | None:
    """Climate TRACE for the same year, grouped like inventory sectors."""
    groups = {"energy": ["power", "transportation", "buildings", "fossil-fuel-operations", "manufacturing",
                         "mineral-extraction", "fluorinated-gases"], "agriculture": ["agriculture"], "waste": ["waste"]}

    async def one(sector):
        r = await http.get("https://api.climatetrace.org/v6/country/emissions",
                           params={"since": year, "to": year, "countries": iso3, "sectors": sector})
        rows = r.json() if r.status_code == 200 else []
        return sector, ((rows[0]["emissions"]["co2e_100yr"] or 0) / 1e6 if rows else 0)

    pairs = dict(await asyncio.gather(*(one(s) for g in groups.values() for s in g)))
    out = {g: round(sum(pairs[s] for s in secs), 3) for g, secs in groups.items()}
    out["total"] = round(sum(out.values()), 3)
    out["sectors"] = {s: round(v, 3) for s, v in pairs.items()}
    return out if out["total"] > 0 else None


async def research(iso3: str) -> AsyncIterator[dict]:
    """Run one research agent. Yields step events, then {'type': 'result', 'finding': ...}."""
    c = data.find(iso3)
    if not c:
        yield {"type": "error", "message": "Unknown country."}
        return
    name, iso3 = c["name"], c["iso3"]
    oai = AsyncOpenAI()
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as http:
        yield {"type": "step", "text": f"Searching for {name}'s latest UN inventory"}
        queries = [f"{name} biennial transparency report national greenhouse gas inventory total emissions excluding LULUCF",
                   f"{name} national GHG inventory total emissions MtCO2e excluding LULUCF UNFCCC"]
        try:
            batches = await asyncio.gather(*(_search(http, q) for q in queries))
        except Exception:
            yield {"type": "error", "message": "Web search is unavailable right now."}
            return
        results, seen = [], set()
        for r in (x for b in zip(*batches) for x in b):  # interleave the two queries
            if r["url"] not in seen:
                seen.add(r["url"])
                results.append(r)
        complete = [r for r in results if not r["url"].endswith("...")]  # search sometimes truncates URLs
        results = (complete if len(complete) >= 4 else results)[:8]
        yield {"type": "step", "text": f"{len(results)} sources found, reading the most relevant"}
        official = sorted(results[:6], key=lambda r: ("unfccc.int" not in r["url"] and ".gov" not in r["url"]))
        pages = await asyncio.gather(*(_fetch(http, r["url"]) for r in official[:3]))
        texts = {r["url"]: (r.get("snippet") or "") for r in results}
        for r, p in zip(official[:3], pages):
            if p:
                texts[r["url"]] = p
        titles = {r["url"]: r.get("title") or r["url"] for r in results}
        yield {"type": "step", "text": f"Extracting the declared total with {EXTRACT_MODEL}"}
        sources = "\n\n".join(f"[{i + 1}] {titles[u]}\nURL: {u}\n{t}" for i, (u, t) in enumerate(texts.items()))
        try:
            resp = await oai.responses.create(
                model=EXTRACT_MODEL, reasoning={"effort": "low"},
                input=PROMPT.format(name=name, min_year=MIN_YEAR, sources=sources),
                text={"format": {"type": "json_schema", "name": "inventory", "strict": True, "schema": SCHEMA}})
            x = json.loads(resp.output_text)
        except Exception:
            yield {"type": "error", "message": "Extraction failed."}
            return

        finding = {"iso3": iso3, "status": "not_found", "notes": x.get("notes")}
        ok = x["found"] and x["year"] and x["total_mt"] and x["year"] >= MIN_YEAR and x["source_url"] in texts
        if ok and _norm(x["quote"])[:60] not in _norm(texts[x["source_url"]]):
            ok, finding["notes"] = False, "Rejected: the quote was not found in the cited source."
        if ok:
            yield {"type": "step", "text": f"Found {x['total_mt']:,.0f} Mt for {x['year']}. Fetching Climate TRACE for the same year"}
            observed = await _observed(http, iso3, x["year"])
            finding.update(status="found", year=x["year"], total_mt=x["total_mt"], energy_mt=x["energy_mt"],
                           agriculture_mt=x["agriculture_mt"], waste_mt=x["waste_mt"], observed=observed,
                           document=x["document"], source_url=x["source_url"], source_title=titles[x["source_url"]],
                           quote=x["quote"], confidence=x["confidence"])
        else:
            yield {"type": "step", "text": "No usable official total found"}
        await asyncio.to_thread(store.save, finding)
        data.invalidate()
        yield {"type": "result", "finding": finding}


async def research_many(isos: list[str], concurrency: int = 6) -> list[dict]:
    """Run several research agents in parallel."""
    sem = asyncio.Semaphore(concurrency)

    async def one(iso):
        async with sem:
            last = None
            async for ev in research(iso):
                if ev["type"] == "step":
                    print(f"[{iso}] {ev['text']}", flush=True)
                last = ev
            return last
    return await asyncio.gather(*(one(i) for i in isos))
