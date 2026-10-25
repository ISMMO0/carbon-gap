"""End-to-end smoke test of the API (no AI calls). Run with the server up:
.venv/bin/python -m scripts.smoke_test [base_url]
"""
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8010"


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    return ok


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    results = [
        check("front-end served", c.get("/").status_code == 200 and "Carbon Gap" in c.get("/").text),
        check("health", c.get("/api/health").json()["ok"]),
    ]
    countries = c.get("/api/countries").json()["countries"]
    compared = [x for x in countries if x.get("declared") is not None]
    results += [
        check(f"countries ({len(countries)}, {len(compared)} compared)", len(compared) >= 60),
        check("gap fields consistent", all(abs(x["observed"] - x["declared"] - x["gap"]) < 1e-3 for x in compared)),
        check("market data", len(c.get("/api/market").json()["countries"]) >= 25),
    ]
    companies = c.get("/api/companies").json()["companies"]
    results += [
        check(f"companies ({len(companies)})", len(companies) >= 40),
        check("every reported figure has a source and quote",
              all(x["reported"]["source_url"] and x["reported"]["quote"] for x in companies if x["reported"])),
        check("sites endpoint", len(c.get("/api/countries/POL/sites").json()["sites"]) > 0),
    ]
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
