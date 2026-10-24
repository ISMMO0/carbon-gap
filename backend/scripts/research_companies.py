"""Run company research agents (self-reported Scope 1) in parallel.

Run: .venv/bin/python -m scripts.research_companies [N] [CONCURRENCY]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import data, research  # noqa: E402

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    conc = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    todo = data.companies()[:n]
    for c, ev in zip(todo, asyncio.run(research.research_many(todo, conc))):
        f = (ev or {}).get("finding") or {}
        print(f"{c['name'][:28]:28} {f.get('status') or (ev or {}).get('message')} {f.get('year') or ''} {f.get('scope1_mt') or ''}")
