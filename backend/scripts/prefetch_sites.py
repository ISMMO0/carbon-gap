"""Pre-fetch the largest Climate TRACE sites of every country into the disk cache, so the map shows them instantly.

Run: .venv/bin/python -m scripts.prefetch_sites
"""
from concurrent.futures import ThreadPoolExecutor

from app import data


def one(iso):
    try:
        return iso, len(data.sites(iso, 60))
    except Exception:
        return iso, -1


if __name__ == "__main__":
    isos = [c["iso3"] for c in data.all_countries()]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, isos))
    print(f"{sum(1 for _, n in res if n > 0)}/{len(isos)} countries with sites, {sum(n for _, n in res if n > 0)} sites cached")
