"""Look for newer national inventories than the Climate Watch ones (e.g. 2023 data submitted in 2025).
A newer figure found by an agent replaces the older one, still compared with Climate TRACE for the same year.

Run: .venv/bin/python -m scripts.research_updates [MAX_YEAR] [CONCURRENCY]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import data, research  # noqa: E402

if __name__ == "__main__":
    max_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2021
    conc = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    base = data.load()["countries"]
    todo = sorted((c for c in base.values() if c["year"] <= max_year), key=lambda c: -c["declared"]["total"])
    print(f"{len(todo)} countries with an inventory from {max_year} or older", flush=True)
    asyncio.run(research.research_many([c["iso3"] for c in todo], conc))
