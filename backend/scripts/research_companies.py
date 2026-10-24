"""Run company research agents (self-reported Scope 1) in parallel.

Run: .venv/bin/python -m scripts.research_companies [N] [CONCURRENCY]   or   ... [company-id ...]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import data, research  # noqa: E402

if __name__ == "__main__":
    nums = [int(a) for a in sys.argv[1:] if a.isdigit()]
    n, conc = (nums + [40, 3])[:2] if len(nums) < 2 else nums[:2]
    ids = [a for a in sys.argv[1:] if not a.isdigit()]
    todo = [c for c in data.companies() if c["id"] in ids] if ids else data.companies()[:n]
    for c, ev in zip(todo, asyncio.run(research.research_many(todo, conc))):
        f = (ev or {}).get("finding") or {}
        print(f"{c['name'][:28]:28} {f.get('status') or (ev or {}).get('message')} {f.get('year') or ''} {f.get('scope1_mt') or ''}")
