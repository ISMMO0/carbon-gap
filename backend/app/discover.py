"""Discover any company on demand.

1. Profile it with OpenAI (Responses API + web_search + Structured Outputs): subsidiaries, countries with large
   emitting facilities, relevant sectors.
2. Find its sites in Climate TRACE: assets in those countries whose owners match the company or a subsidiary
   (emissions split equally between co-owners).
3. Find what it reports (Scope 1) with the company research agent (Keenable + GPT, quote-checked).
"""
import asyncio
import json
import re
from collections import defaultdict
from collections.abc import AsyncIterator

import httpx

from . import data, llm, research, store

MODEL = "gpt-5.5"
YEARS = [2023, 2024]
CT_SECTORS = ["power", "manufacturing", "fossil-fuel-operations", "mineral-extraction"]

PROFILE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["found", "name", "aliases", "hq_country", "industry", "countries", "sectors", "summary"],
    "properties": {
        "found": {"type": "boolean", "description": "False if this is not a real company with physical emitting operations."},
        "name": {"type": "string", "description": "Short common name of the group, e.g. 'TotalEnergies'."},
        "aliases": {"type": "array", "items": {"type": "string"},
                    "description": "Legal names and main subsidiaries that own plants, refineries, mines or mills (max 12)."},
        "hq_country": {"type": "string", "description": "ISO3 code of the headquarters country."},
        "industry": {"type": "string", "description": "e.g. 'Oil & gas', 'Steel', 'Utilities', 'Cement', 'Mining'."},
        "countries": {"type": "array", "items": {"type": "string"},
                      "description": "ISO3 codes of the countries with its largest emitting facilities (max 8)."},
        "sectors": {"type": "array", "items": {"type": "string", "enum": CT_SECTORS}},
        "summary": {"type": "string", "description": "One sentence on what the company does and where it emits."},
    },
}


def _norm(s: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip() + " "


async def _profile(name: str) -> dict:
    resp = await llm.respond(
        model=MODEL, reasoning={"effort": "low"}, tools=[{"type": "web_search"}],
        input=f"Profile the company '{name}' for an emissions investigation: its group name, the legal entities and "
              f"subsidiaries that own its plants, refineries, mines or mills, and the countries where its largest "
              f"emitting facilities are. Search the web if needed.",
        text={"format": {"type": "json_schema", "name": "profile", "strict": True, "schema": PROFILE_SCHEMA}})
    return json.loads(resp.output_text)


async def _sites(profile: dict) -> tuple[dict, list]:
    """Observed emissions per year and the matched assets."""
    keys = [_norm(a) for a in [profile["name"], *profile["aliases"]] if len(a.strip()) >= 4]
    countries = [c.upper() for c in profile["countries"][:8]] or [profile["hq_country"].upper()]
    sectors = profile["sectors"] or CT_SECTORS
    sem = asyncio.Semaphore(8)

    async def fetch(http, country, sector, year):
        async with sem:
            try:
                r = await http.get("https://api.climatetrace.org/v6/assets",
                                   params={"countries": country, "sectors": sector, "year": year, "limit": 1000})
                return year, (r.json().get("assets") or []) if r.status_code == 200 else []
            except httpx.HTTPError:
                return year, []

    async with httpx.AsyncClient(timeout=60) as http:
        batches = await asyncio.gather(*(fetch(http, c, s, y) for c in countries for s in sectors for y in YEARS))
    observed, assets, seen = defaultdict(float), {}, set()
    for year, rows in batches:
        for a in rows:
            if (a["Id"], year) in seen:
                continue
            seen.add((a["Id"], year))
            owners = {o["CompanyId"]: o["CompanyName"] for o in a.get("Owners") or [] if o.get("CompanyId")}
            mine = [n for n in owners.values() if any(k in _norm(n) for k in keys)]
            em = sum((e.get("EmissionsQuantity") or 0) for e in a.get("EmissionsSummary") or [] if e.get("Gas") == "co2e_100yr") / 1e6
            if not mine or em <= 0:
                continue
            share = em * len(mine) / len(owners)
            observed[str(year)] += share
            geo = (a.get("Centroid") or {}).get("Geometry")
            if year == YEARS[-1] and geo:
                assets[str(a["Id"])] = {"id": str(a["Id"]), "name": a["Name"], "country": a["Country"],
                                        "kind": data._site_kind(a.get("Sector", ""), a.get("AssetType") or ""),
                                        "observed": round(share, 3), "coord": geo, "shared_with": len(owners) - len(mine)}
    return {y: round(v, 3) for y, v in observed.items()}, sorted(assets.values(), key=lambda x: -x["observed"])


async def discover(name: str) -> AsyncIterator[dict]:
    """Yields step events, then {'type': 'result', 'company_id': ...}."""
    yield {"type": "step", "text": f"Profiling {name} with {MODEL} and web search"}
    try:
        p = await _profile(name)
    except Exception:
        yield {"type": "error", "message": "Could not profile this company."}
        return
    if not p["found"]:
        yield {"type": "error", "message": f"{name} does not look like a company with physical emitting operations."}
        return
    cid = re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")
    yield {"type": "step", "text": f"{p['name']}: {p['industry']}, facilities in {', '.join(p['countries'][:8])}. Scanning Climate TRACE sites"}
    observed, assets = await _sites(p)
    total = observed.get(str(YEARS[-1]), 0)
    yield {"type": "step", "text": f"{len(assets)} sites matched, {total:,.1f} Mt observed in {YEARS[-1]}" if assets
           else "No matching sites in Climate TRACE for these countries"}
    company = {"id": cid, "name": p["name"], "subsidiaries": p["aliases"][:12], "industry": p["industry"],
               "summary": p["summary"], "hq_country": p["hq_country"], "discovered": True,
               "observed": {str(y): observed.get(str(y), 0) for y in YEARS},
               "countries": sorted({a["country"] for a in assets}) or [c.upper() for c in p["countries"]],
               "asset_count": len(assets), "kinds": sorted({a["kind"] for a in assets}), "assets": assets[:30]}
    await asyncio.to_thread(store.save_company_profile, company)
    data.invalidate()
    async for ev in research.research_company(company):
        if ev["type"] in ("step", "error"):
            yield ev
    data.invalidate()
    yield {"type": "result", "company_id": cid}
