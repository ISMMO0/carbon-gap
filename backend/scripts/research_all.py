"""Research every country that still has no declaration (including past failures), in parallel.

Run: .venv/bin/python -m scripts.research_all [CONCURRENCY]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import data, research  # noqa: E402

if __name__ == "__main__":
    conc = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    todo = sorted(data.undeclared().values(), key=lambda c: -(c["observed_latest"] or {}).get("total", 0))
    print(f"{len(todo)} countries to research", flush=True)
    asyncio.run(research.research_many([c["iso3"] for c in todo], conc))
