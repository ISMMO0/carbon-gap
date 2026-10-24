"""Build data/companies.json: observed emissions of the largest companies, from Climate TRACE assets.

1. Fetch large assets (power, manufacturing, fossil fuel operations, mining) in major emitting countries.
2. Attribute each asset's emissions equally to its distinct owners (Climate TRACE gives no ownership shares).
3. Group subsidiaries under their parent company with GPT-5.5 (Structured Outputs).
Observed = emissions of the assets Climate TRACE tracks for that company: partial coverage by construction.

Run: .venv/bin/python -m scripts.build_companies
"""
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
from openai import OpenAI  # noqa: E402

OUT = ROOT / "data" / "companies.json"
YEARS = [2023, 2024]
COUNTRIES = ["DEU", "POL", "CZE", "ITA", "ESP", "FRA", "NLD", "GBR", "BEL", "AUT", "USA", "CAN", "AUS", "JPN",
             "KOR", "IND", "CHN", "ZAF", "BRA", "MEX", "IDN", "SAU", "RUS", "TUR"]
SECTORS = ["power", "manufacturing", "fossil-fuel-operations", "mineral-extraction"]
TOP_OWNERS = 160
TOP_COMPANIES = 40

client = httpx.Client(timeout=90)


def fetch(job):
    country, sector, year = job
    r = client.get("https://api.climatetrace.org/v6/assets",
                   params={"countries": country, "sectors": sector, "year": year, "limit": 1000})
    return year, (r.json().get("assets") or []) if r.status_code == 200 else []


def emissions(a) -> float:
    return sum((e.get("EmissionsQuantity") or 0) for e in a.get("EmissionsSummary") or [] if e.get("Gas") == "co2e_100yr") / 1e6


def kind(a) -> str:
    s = f"{a.get('Sector', '')} {a.get('AssetType') or ''}".lower()
    for k, words in (("power", ("electricity", "power")), ("steel", ("steel", "iron")), ("cement", ("cement",)),
                     ("oil", ("oil", "gas", "refin")), ("mining", ("coal", "mining", "ore", "quarr"))):
        if any(w in s for w in words):
            return k
    return "other"


def main():
    jobs = [(c, s, y) for c in COUNTRIES for s in SECTORS for y in YEARS]
    owner_names, by_owner = {}, defaultdict(lambda: {y: 0.0 for y in YEARS})
    assets = defaultdict(dict)  # owner id -> asset id -> asset summary (latest year)
    seen = set()
    with ThreadPoolExecutor(8) as ex:
        for year, rows in ex.map(fetch, jobs):
            for a in rows:
                if (a["Id"], year) in seen:
                    continue
                seen.add((a["Id"], year))
                owners = {o["CompanyId"]: o["CompanyName"].strip() for o in a.get("Owners") or [] if o.get("CompanyId")}
                em = emissions(a)
                geo = (a.get("Centroid") or {}).get("Geometry")
                if not owners or em <= 0:
                    continue
                for oid, name in owners.items():
                    owner_names[oid] = name
                    by_owner[oid][year] += em / len(owners)
                    if year == YEARS[-1] and geo:
                        assets[oid][str(a["Id"])] = {"id": str(a["Id"]), "name": a["Name"], "country": a["Country"],
                                                     "kind": kind(a), "observed": round(em / len(owners), 3),
                                                     "coord": geo, "shared_with": len(owners) - 1}
    print(f"{len(seen)} asset-years, {len(owner_names)} owners")
    top = sorted(by_owner, key=lambda o: -by_owner[o][YEARS[-1]])[:TOP_OWNERS]

    # Group subsidiaries under parents with GPT-5.5
    schema = {"type": "object", "additionalProperties": False, "required": ["groups"], "properties": {"groups": {
        "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["parent", "ids"],
                                   "properties": {"parent": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}}}}}}}
    listing = "\n".join(f"{o}: {owner_names[o]}" for o in top)
    resp = OpenAI().responses.create(
        model="gpt-5.5", reasoning={"effort": "low"},
        input="Group these companies under their ultimate parent company (e.g. subsidiaries of PGE under 'PGE', "
              "of ArcelorMittal under 'ArcelorMittal'). Use the short, common parent name. Governments and state "
              "agencies keep their own name. Every id must appear exactly once.\n\n" + listing,
        text={"format": {"type": "json_schema", "name": "groups", "strict": True, "schema": schema}})
    groups = json.loads(resp.output_text)["groups"]

    companies = []
    for g in groups:
        ids = [i for i in g["ids"] if i in by_owner]
        if not ids:
            continue
        merged = {}
        for i in ids:
            for aid, a in assets[i].items():
                merged[aid] = {**a, "observed": round(merged.get(aid, {}).get("observed", 0) + a["observed"], 3)}
        site_list = sorted(merged.values(), key=lambda a: -a["observed"])
        slug = re.sub(r"[^a-z0-9]+", "-", g["parent"].lower()).strip("-")
        companies.append({
            "id": slug, "name": g["parent"], "subsidiaries": sorted({owner_names[i] for i in ids}),
            "observed": {str(y): round(sum(by_owner[i][y] for i in ids), 3) for y in YEARS},
            "countries": sorted({a["country"] for a in site_list}), "asset_count": len(site_list),
            "kinds": sorted({a["kind"] for a in site_list}), "assets": site_list[:30],
        })
    companies.sort(key=lambda c: -c["observed"][str(YEARS[-1])])
    OUT.write_text(json.dumps({"years": YEARS, "countries_scanned": COUNTRIES, "companies": companies[:TOP_COMPANIES]},
                              ensure_ascii=False, indent=1))
    for c in companies[:15]:
        print(f"{c['name'][:30]:30} {c['observed'][str(YEARS[-1])]:8.1f} Mt  {c['asset_count']} assets  {','.join(c['countries'][:6])}")


if __name__ == "__main__":
    main()
