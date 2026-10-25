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

from . import data, llm, store

KEENABLE = "https://api.keenable.ai/v1"
EXTRACT_MODEL = llm.MODEL
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


async def _read_sources(http: httpx.AsyncClient, queries: list[str], prefer: tuple[str, ...]) -> tuple[dict, dict]:
    """Search, then read the 3 most promising pages. Returns ({url: text}, {url: title})."""
    batches = await asyncio.gather(*(_search(http, q) for q in queries))
    results, seen = [], set()
    for r in (x for b in zip(*batches) for x in b):  # interleave the queries
        if r["url"] not in seen:
            seen.add(r["url"])
            results.append(r)
    complete = [r for r in results if not r["url"].endswith("...")]  # search sometimes truncates URLs
    results = (complete if len(complete) >= 4 else results)[:8]
    best = sorted(results[:6], key=lambda r: not any(p in r["url"] for p in prefer))[:3]
    pages = await asyncio.gather(*(_fetch(http, r["url"]) for r in best))
    texts = {r["url"]: (r.get("snippet") or "") for r in results}
    texts.update({r["url"]: p for r, p in zip(best, pages) if p})
    return texts, {r["url"]: r.get("title") or r["url"] for r in results}


async def _extract(prompt: str, name: str, schema: dict, texts: dict, titles: dict) -> dict:
    sources = "\n\n".join(f"[{i + 1}] {titles[u]}\nURL: {u}\n{t}" for i, (u, t) in enumerate(texts.items()))
    resp = await llm.respond(
        model=EXTRACT_MODEL, reasoning={"effort": "low"}, input=prompt.format(sources=sources),
        text={"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}})
    return json.loads(resp.output_text)


WEB_RULES = """Search the web (prefer official sources: unfccc.int, government sites, the company's own reports).
Return the source_url of the page or PDF that states the figure, and a short verbatim quote from it that contains the
number. If you cannot find a figure that satisfies every rule, set found=false. Never guess."""


async def _web_pass(http: httpx.AsyncClient, task: str, name: str, schema: dict) -> tuple[dict, dict, dict]:
    """Second pass with OpenAI's own web search. The quote is then checked against the page itself (read via Keenable)."""
    resp = await llm.respond(
        model=EXTRACT_MODEL, reasoning={"effort": "low"}, tools=[{"type": "web_search"}],
        input=task + "\n\n" + WEB_RULES,
        text={"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}})
    x = json.loads(resp.output_text)
    texts, titles = {}, {}
    if x.get("found") and x.get("source_url", "").startswith("http"):
        page = await _fetch(http, x["source_url"])
        cited = {a.url: a.title for item in resp.output for part in getattr(item, "content", None) or []
                 for a in getattr(part, "annotations", None) or [] if getattr(a, "type", "") == "url_citation"}
        if page:
            texts[x["source_url"]] = page
        elif x["source_url"] in cited:  # page unreadable (often a large PDF): keep it, flagged as not machine-checked
            texts[x["source_url"]] = x["quote"]
            x["confidence"] = "low"
            x["notes"] = (x.get("notes") or "") + " Quote not machine-checked (source not readable)."
        titles[x["source_url"]] = cited.get(x["source_url"]) or x.get("document") or x["source_url"]
    return x, texts, titles


SOCIAL = ("linkedin.com", "facebook.com", "x.com/", "twitter.com", "reddit.com", "instagram.com", "tiktok.com")


def _quote_ok(x: dict, texts: dict) -> bool:
    """The cited quote must appear in the cited source, and the source must not be a social network post:
    our guard against invented or second-hand numbers."""
    url = x.get("source_url") or ""
    return url in texts and not any(d in url for d in SOCIAL) and _norm(x["quote"])[:60] in _norm(texts[url])


async def research(iso3: str) -> AsyncIterator[dict]:
    """Country research agent. Yields step events, then {'type': 'result', 'finding': ...}."""
    c = data.find(iso3)
    if not c:
        yield {"type": "error", "message": "Unknown country."}
        return
    name, iso3 = c["name"], c["iso3"]
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as http:
        yield {"type": "step", "text": f"Searching for {name}'s latest UN inventory"}
        try:
            texts, titles = await _read_sources(http, [
                f"{name} biennial transparency report national greenhouse gas inventory total emissions excluding LULUCF",
                f"{name} national GHG inventory total emissions MtCO2e excluding LULUCF UNFCCC"], ("unfccc.int", ".gov"))
        except Exception:
            yield {"type": "error", "message": "Web search is unavailable right now."}
            return
        yield {"type": "step", "text": f"{len(texts)} sources found. Extracting the declared total with {EXTRACT_MODEL}"}
        try:
            x = await _extract(PROMPT.replace("{name}", name).replace("{min_year}", str(MIN_YEAR)), "inventory", SCHEMA, texts, titles)
        except Exception:
            yield {"type": "error", "message": "Extraction failed."}
            return
        good = lambda x, texts: x["found"] and x["year"] and x["total_mt"] and x["year"] >= MIN_YEAR and _quote_ok(x, texts)
        if not good(x, texts):
            yield {"type": "step", "text": "Second pass with OpenAI web search"}
            try:
                task = PROMPT.split("SOURCES:")[0].replace("{name}", name).replace("{min_year}", str(MIN_YEAR)).replace(
                    "Use only the sources below. Never use your own memory for numbers.", "Use web search. Never use memory for numbers.")
                x2, t2, ti2 = await _web_pass(http, task, "inventory", SCHEMA)
                if good(x2, t2):
                    x, texts, titles = x2, t2, ti2
            except Exception:
                pass
        finding = {"iso3": iso3, "status": "not_found", "notes": x.get("notes")}
        ok = good(x, texts)
        if x["found"] and not _quote_ok(x, texts):
            finding["notes"] = "Rejected: the quote was not found in the cited source."
        if ok:
            yield {"type": "step", "text": f"Found {x['total_mt']:,.0f} Mt for {x['year']}. Fetching Climate TRACE for the same year"}
            observed = await _observed(http, iso3, x["year"])
            if not observed or not data.plausible(x["total_mt"], observed["total"]):
                finding["notes"] = f"Rejected as implausible: {x['total_mt']:,.1f} Mt declared vs {(observed or {}).get('total', 0):,.1f} Mt observed (unit or scope error)."
                yield {"type": "step", "text": "Figure rejected as implausible (unit or scope error)"}
                await asyncio.to_thread(store.save, finding)
                data.invalidate()
                yield {"type": "result", "finding": finding}
                return
            finding.update(status="found", year=x["year"], total_mt=x["total_mt"], energy_mt=x["energy_mt"],
                           agriculture_mt=x["agriculture_mt"], waste_mt=x["waste_mt"], observed=observed,
                           document=x["document"], source_url=x["source_url"], source_title=titles[x["source_url"]],
                           quote=x["quote"], confidence=x["confidence"])
        else:
            yield {"type": "step", "text": "No usable official total found"}
        await asyncio.to_thread(store.save, finding)
        data.invalidate()
        yield {"type": "result", "finding": finding}


COMPANY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["found", "year", "scope1_mt", "document", "source_url", "quote", "confidence", "notes"],
    "properties": {
        "found": {"type": "boolean", "description": "True only if the company's own reported Scope 1 total is stated."},
        "year": {"type": ["integer", "null"], "description": "Reporting year (fiscal year end) the Scope 1 figure refers to."},
        "scope1_mt": {"type": ["number", "null"], "description": "Group Scope 1 emissions in MtCO2e (1 Mt = 1,000,000 t)."},
        "document": {"type": "string", "description": "Report name, e.g. 'Sustainability Report 2024'."},
        "source_url": {"type": "string", "description": "One of the provided URLs."},
        "quote": {"type": "string", "description": "Verbatim text from that source containing the Scope 1 figure."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"],
                       "description": "high = company report or filing; medium = reputable outlet or database; low = unclear."},
        "notes": {"type": "string", "description": "Boundary (operational control / equity share), unit conversion, caveats."},
    },
}

COMPANY_PROMPT = """You are a climate data researcher. Find the latest Scope 1 greenhouse-gas emissions that {name}
reported itself (sustainability report, annual report, CDP response, CSRD statement), for reporting year 2022 or later.
{hint}
Rules:
- Use only the sources below. Never use your own memory for numbers.
- Scope 1 only (not Scope 2 or 3, not total). Group level. Convert to MtCO2e (tonnes / 1,000,000; million tonnes = Mt).
- Read the unit in table headers carefully (t, kt, '000 t, million t, MtCO2e). Sanity check: the large sites tracked
  for this company alone emit about {tracked} MtCO2e per year, so its group Scope 1 should be of that order or larger.
- source_url must be one of the URLs below, and quote must be copied word for word from that source.
- Prefer the company's own report and the latest year.

SOURCES:
{sources}"""


async def research_company(company: dict) -> AsyncIterator[dict]:
    """Company research agent: finds the company's self-reported Scope 1 emissions."""
    name = company["name"]
    hint = f"Known subsidiaries: {', '.join(company.get('subsidiaries', [])[:6])}." if company.get("subsidiaries") else ""
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as http:
        yield {"type": "step", "text": f"Searching {name}'s sustainability reports"}
        try:
            texts, titles = await _read_sources(http, [
                f"{name} scope 1 greenhouse gas emissions 2024 tCO2e sustainability report",
                f"{name} annual report direct GHG emissions scope 1 million tonnes CO2e"], ("report", "sustainab", "esg", ".pdf"))
        except Exception:
            yield {"type": "error", "message": "Web search is unavailable right now."}
            return
        yield {"type": "step", "text": f"{len(texts)} sources found. Extracting Scope 1 with {EXTRACT_MODEL}"}
        try:
            tracked = max(company["observed"].values() or [0])
            prompt = COMPANY_PROMPT.replace("{name}", name).replace("{hint}", hint).replace("{tracked}", f"{tracked:,.0f}")
            x = await _extract(prompt, "scope1", COMPANY_SCHEMA, texts, titles)
        except Exception:
            yield {"type": "error", "message": "Extraction failed."}
            return
        tracked = max(company["observed"].values() or [0])
        plausible = lambda x: not (x["scope1_mt"] and tracked and x["scope1_mt"] < tracked / 3)
        if not (x["found"] and x["year"] and x["scope1_mt"] and plausible(x) and _quote_ok(x, texts)):
            yield {"type": "step", "text": "Second pass with OpenAI web search"}
            try:
                task = prompt.split("SOURCES:")[0].replace("Use only the sources below. Never use your own memory for numbers.",
                                                         "Use web search. Never use memory for numbers.")
                x2, t2, ti2 = await _web_pass(http, task, "scope1", COMPANY_SCHEMA)
                if x2["found"] and x2["year"] and x2["scope1_mt"] and plausible(x2) and _quote_ok(x2, t2):
                    x, texts, titles = x2, t2, ti2
            except Exception:
                pass
        finding = {"key": company["id"], "status": "not_found", "notes": x.get("notes")}
        if x["found"] and x["scope1_mt"] and tracked and x["scope1_mt"] < tracked / 3:
            x["found"] = False  # far below its own tracked sites: almost always a unit or scope mix-up
            finding["notes"] = f"Rejected as implausible: {x['scope1_mt']} Mt is far below the {tracked:.0f} Mt of tracked sites."
        if x["found"] and x["year"] and x["scope1_mt"] and _quote_ok(x, texts):
            finding.update(status="found", year=x["year"], scope1_mt=x["scope1_mt"], document=x["document"],
                           source_url=x["source_url"], source_title=titles[x["source_url"]], quote=x["quote"],
                           confidence=x["confidence"])
            yield {"type": "step", "text": f"Found {x['scope1_mt']:,.1f} Mt Scope 1 for {x['year']}"}
        else:
            if x["found"]:
                finding["notes"] = "Rejected: the quote was not found in the cited source."
            elif x["scope1_mt"] and "implausible" in (finding["notes"] or ""):
                yield {"type": "step", "text": finding["notes"]}
            yield {"type": "step", "text": "No usable self-reported Scope 1 found"}
        await asyncio.to_thread(store.save_company, finding)
        data.invalidate()
        yield {"type": "result", "finding": finding}


async def research_many(isos: list, concurrency: int = 6) -> list[dict]:
    """Run several research agents in parallel (countries as ISO3 codes, companies as dicts)."""
    sem = asyncio.Semaphore(concurrency)

    async def one(iso):  # an ISO3 code (country) or a company dict
        tag = iso if isinstance(iso, str) else iso["id"]
        async with sem:
            last = None
            agent = research(iso) if isinstance(iso, str) else research_company(iso)
            async for ev in agent:
                if ev["type"] == "step":
                    print(f"[{tag}] {ev['text']}", flush=True)
                last = ev
            return last
    return await asyncio.gather(*(one(i) for i in isos))


async def swarm(isos: list[str], concurrency: int = 3) -> AsyncIterator[dict]:
    """Run country agents in parallel and merge their events into one stream, each tagged with its agent."""
    queue: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(concurrency)

    async def run(iso):
        async with sem:
            await queue.put({"type": "start", "agent": iso})
            status = "error"
            try:
                async for ev in research(iso):
                    if ev["type"] == "result":
                        status = ev["finding"]["status"]
                        await queue.put({"type": "done", "agent": iso, "status": status, "finding": {
                            k: ev["finding"].get(k) for k in ("year", "total_mt", "document", "confidence")}})
                    else:
                        await queue.put({**ev, "agent": iso})
            except Exception:
                await queue.put({"type": "done", "agent": iso, "status": "error"})

    tasks = [asyncio.create_task(run(i)) for i in isos]
    pending = len(tasks)
    while pending:
        ev = await queue.get()
        if ev["type"] == "done":
            pending -= 1
        yield ev
