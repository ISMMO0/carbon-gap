"""Build data/market.json: EU ETS free allocation vs verified emissions per country and sector.

Source: EEA EU ETS Union Registry data, packaged by datahub.io (github.com/datasets/eu-emissions-trading-system),
saved to data/raw/eu-ets.csv. Stationary installations only (aviation excluded).
A country's "shortfall" = verified emissions - free allowances: allowances its installations had to buy
(auctions or market). Negative = surplus of free allowances.

Run: .venv/bin/python -m scripts.build_market
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import pycountry

DATA = Path(__file__).resolve().parents[1] / "data"
VERIFIED, FREE = "2. Verified emissions", "1.1 Freely allocated allowances"
SECTORS = {
    "Power & heat": {"20"},
    "Refining": {"21"},
    "Iron & steel": {"22", "23", "24", "25"},
    "Cement & lime": {"29", "30"},
    "Chemicals": {str(c) for c in range(37, 45)},
    "Other industry": {"26", "27", "28", "31", "32", "33", "34", "35", "36", "45", "99"},
}
CODE_TO_SECTOR = {c: s for s, codes in SECTORS.items() for c in codes}


def main():
    v = defaultdict(float)  # (iso2, code, year) -> t
    f = defaultdict(float)
    for r in csv.DictReader((DATA / "raw" / "eu-ets.csv").open()):
        if not r["year"].isdigit() or not r["value"]:
            continue
        key = (r["country_code"], r["main_activity_code"], int(r["year"]))
        if r["citl_information"] == VERIFIED:
            v[key] += float(r["value"])
        elif r["citl_information"] == FREE:
            f[key] += float(r["value"])
    year = max(y for (_, code, y), val in v.items() if code == "20-99" and val > 0)
    countries = {}
    for iso2 in sorted({k[0] for k in v}):
        c = pycountry.countries.get(alpha_2=iso2)
        verified = v[(iso2, "20-99", year)] / 1e6
        if not c or verified <= 0:
            continue
        free = f[(iso2, "20-99", year)] / 1e6
        sectors = []
        for name, codes in SECTORS.items():
            sv = sum(v[(iso2, code, year)] for code in codes) / 1e6
            sf = sum(f[(iso2, code, year)] for code in codes) / 1e6
            if sv > 0.01 or sf > 0.01:
                sectors.append({"sector": name, "verified": round(sv, 3), "free": round(sf, 3)})
        history = [{"year": y, "verified": round(v[(iso2, "20-99", y)] / 1e6, 2), "free": round(f[(iso2, "20-99", y)] / 1e6, 2)}
                   for y in range(2013, year + 1)]
        countries[c.alpha_3] = {"iso3": c.alpha_3, "name": getattr(c, "common_name", None) or c.name,
                                "verified": round(verified, 3), "free": round(free, 3),
                                "shortfall": round(verified - free, 3), "sectors": sectors, "history": history}
    out = {"year": year, "source": "EEA EU ETS Union Registry data (via datahub.io)", "countries": countries}
    (DATA / "market.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{len(countries)} countries, year {year}")


if __name__ == "__main__":
    main()
