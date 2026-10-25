"""Discover companies in parallel (profile → Climate TRACE sites → reported Scope 1).

Run: .venv/bin/python -m scripts.discover_companies "Shell" "BP" ...   (no names = the default list)
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import discover  # noqa: E402

DEFAULT = ["Shell", "BP", "Chevron", "Eni", "Equinor", "Repsol", "ArcelorMittal", "Holcim", "Heidelberg Materials",
           "Thyssenkrupp", "RWE", "Uniper", "EnBW", "Vattenfall", "EDF", "Engie", "Enel", "Iberdrola", "CEZ", "LEAG",
           "BASF", "Glencore", "BHP", "Rio Tinto", "Vale", "Petrobras", "Pemex", "Saint-Gobain", "Orlen", "Fortum"]


async def main(names):
    sem = asyncio.Semaphore(3)

    async def one(name):
        async with sem:
            last = None
            async for ev in discover.discover(name):
                print(f"[{name}] {ev.get('text') or ev.get('message') or ev}", flush=True)
                last = ev
            return last
    await asyncio.gather(*(one(n) for n in names))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or DEFAULT))
