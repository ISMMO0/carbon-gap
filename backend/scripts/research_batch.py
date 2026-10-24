"""Run research agents in parallel on the largest emitters with no UN inventory in our dataset.

Run: .venv/bin/python -m scripts.research_batch [N] [CONCURRENCY]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import data, research  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    conc = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    todo = sorted(data.load()["undeclared"].values(), key=lambda c: -(c["observed_latest"] or {}).get("total", 0))[:n]
    print("researching:", ", ".join(c["name"] for c in todo), flush=True)
    results = asyncio.run(research.research_many([c["iso3"] for c in todo], conc))
    for c, ev in zip(todo, results):
        f = (ev or {}).get("finding") or {}
        print(f"{c['name']:24} {f.get('status', (ev or {}).get('message'))} {f.get('year') or ''} {f.get('total_mt') or ''}")


if __name__ == "__main__":
    main()
