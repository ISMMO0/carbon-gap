"""Build data/countries.json: declared vs observed emissions per country.

Declared  = national inventories reported to the UNFCCC (via Climate Watch API),
            total GHG excluding LULUCF, latest reported year >= 2015.
Observed  = Climate TRACE v6 estimates for the SAME year, all sectors except
            forestry-and-land-use (to match "excluding LULUCF").
Both in MtCO2e (100-year GWP).

Run: .venv/bin/python -m scripts.build_data
"""
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pycountry

OUT = Path(__file__).resolve().parents[1] / "data" / "countries.json"
CW = "https://www.climatewatchdata.org/api/v1/data/historical_emissions"
CT = "https://api.climatetrace.org/v6/country/emissions"
MIN_YEAR, LATEST_CT = 2015, 2024

# Climate TRACE sectors grouped like the UNFCCC inventory sectors.
CT_GROUPS = {
    "energy": ["power", "transportation", "buildings", "fossil-fuel-operations",
               "manufacturing", "mineral-extraction", "fluorinated-gases"],
    "agriculture": ["agriculture"],
    "waste": ["waste"],
}
CT_SECTORS = [s for group in CT_GROUPS.values() for s in group]
# UNFCCC sector name -> group (Annex I and non-Annex I use different labels)
CW_GROUPS = {
    "Energy": "energy",
    "Industrial Processes and Product Use": "energy",
    "Industrial Processes": "energy",
    "Agriculture": "agriculture",
    "Waste": "waste",
}
CW_TOTALS = {"Total GHG emissions without LULUCF", "Total GHG emissions excluding LULUCF/LUCF"}

client = httpx.Client(timeout=60, follow_redirects=True)


def fetch_cw(source_id: int) -> list[dict]:
    first = client.get(CW, params={"source_ids[]": source_id, "per_page": 200, "page": 1})
    pages = -(-int(first.headers["total"]) // 200)

    def page(n):
        r = client.get(CW, params={"source_ids[]": source_id, "per_page": 200, "page": n})
        return r.json()["data"]

    rows = first.json()["data"]
    with ThreadPoolExecutor(8) as ex:
        for chunk in ex.map(page, range(2, pages + 1)):
            rows += chunk
    return rows


def declared() -> dict:
    """iso3 -> {year, source, total, energy, agriculture, waste} (latest year with a total)."""
    series = defaultdict(lambda: defaultdict(dict))  # iso -> key -> year -> value
    source_of = {}
    for sid, label in ((276, "UNFCCC Annex I"), (277, "UNFCCC non-Annex I")):
        for r in fetch_cw(sid):
            if r["gas"] != "Aggregate GHGs":
                continue
            key = "total" if r["sector"] in CW_TOTALS else CW_GROUPS.get(r["sector"])
            if not key:
                continue
            iso = r["iso_code3"]
            source_of[iso] = label
            for e in r["emissions"]:
                if e["value"] is not None:
                    series[iso][key][e["year"]] = series[iso][key].get(e["year"], 0) + e["value"]
    out = {}
    for iso, s in series.items():
        years = [y for y in s.get("total", {}) if y >= MIN_YEAR]
        if not years:
            continue
        y = max(years)
        out[iso] = {"year": y, "source": source_of[iso], "total": s["total"][y],
                    **{g: s[g].get(y) for g in ("energy", "agriculture", "waste")}}
    return out


def observed(years_by_iso: dict, all_isos: list[str]) -> dict:
    """iso3 -> year -> sector -> MtCO2e, for each country's declared year and, for every country, the latest CT year."""
    wanted = defaultdict(set)  # year -> isos
    for iso, y in years_by_iso.items():
        wanted[y].add(iso)
    wanted[LATEST_CT].update(all_isos)
    jobs = []
    for y, isos in wanted.items():
        isos = sorted(isos)
        for i in range(0, len(isos), 60):
            for sector in CT_SECTORS:
                jobs.append((y, sector, isos[i:i + 60]))

    def run(job):
        y, sector, isos = job
        r = client.get(CT, params={"since": y, "to": y, "countries": ",".join(isos), "sectors": sector})
        r.raise_for_status()
        return y, sector, r.json()

    out = defaultdict(lambda: defaultdict(dict))
    with ThreadPoolExecutor(8) as ex:
        for y, sector, rows in ex.map(run, jobs):
            for row in rows:
                out[row["country"]][y][sector] = (row["emissions"]["co2e_100yr"] or 0) / 1e6
    return out


def group(by_sector: dict) -> dict:
    g = {k: sum(by_sector.get(s, 0) for s in secs) for k, secs in CT_GROUPS.items()}
    g["total"] = sum(g.values())
    return g


def main():
    dec = {iso: d for iso, d in declared().items() if pycountry.countries.get(alpha_3=iso)}
    print(f"declared: {len(dec)} countries")
    all_isos = [c["alpha3"] for c in client.get("https://api.climatetrace.org/v6/definitions/countries").json()
                if pycountry.countries.get(alpha_3=c["alpha3"])]
    obs = observed({iso: d["year"] for iso, d in dec.items()}, all_isos)
    countries = {}
    for iso, d in dec.items():
        c = pycountry.countries.get(alpha_3=iso)
        y = d["year"]
        if not c or y not in obs.get(iso, {}):
            continue
        o = group(obs[iso][y])
        if o["total"] <= 0:
            continue
        latest = obs[iso].get(LATEST_CT, {})
        countries[iso] = {
            "iso3": iso,
            "numeric": c.numeric,
            "name": getattr(c, "common_name", None) or c.name,
            "year": y,
            "source": d["source"],
            "declared": {k: (round(d[k], 3) if d[k] is not None else None) for k in ("total", "energy", "agriculture", "waste")},
            "observed": {k: round(v, 3) for k, v in o.items()},
            "observed_sectors": {s: round(v, 3) for s, v in obs[iso][y].items()},
            "observed_latest": {"year": LATEST_CT, "total": round(group(latest)["total"], 3)} if latest else None,
        }
    undeclared = {}
    for iso in all_isos:
        latest = obs.get(iso, {}).get(LATEST_CT)
        if iso in countries or not latest:
            continue
        c = pycountry.countries.get(alpha_3=iso)
        total = group(latest)["total"]
        if total > 0.05:
            undeclared[iso] = {"iso3": iso, "numeric": c.numeric, "name": getattr(c, "common_name", None) or c.name,
                               "observed_latest": {"year": LATEST_CT, "total": round(total, 3)},
                               "observed_sectors": {s: round(v, 3) for s, v in latest.items()}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"countries": countries, "undeclared": undeclared}, ensure_ascii=False, indent=1))
    print(f"wrote {len(countries)} compared + {len(undeclared)} observed-only countries -> {OUT}")


if __name__ == "__main__":
    main()
