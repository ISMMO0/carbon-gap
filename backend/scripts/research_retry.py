"""Re-run research agents for countries whose last run failed or never happened.

Run: .venv/bin/python -m scripts.research_retry ISO3 [ISO3 ...]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import research  # noqa: E402

if __name__ == "__main__":
    for ev in asyncio.run(research.research_many(sys.argv[1:], concurrency=3)):
        f = (ev or {}).get("finding") or {}
        print(f.get("iso3"), f.get("status") or (ev or {}).get("message"), f.get("year") or "", f.get("total_mt") or "")
