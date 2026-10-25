"""Discover companies in parallel (profile → Climate TRACE sites → reported Scope 1).

Run: .venv/bin/python -m scripts.discover_companies "Shell" "BP" ...   (no names = default list, --more = second list)
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
    sem = asyncio.Semaphore(2)

    async def one(name):
        async with sem:
            last = None
            async for ev in discover.discover(name):
                print(f"[{name}] {ev.get('text') or ev.get('message') or ev}", flush=True)
                last = ev
            return last
    await asyncio.gather(*(one(n) for n in names))


MORE = ["Huadian", "SPIC", "HBIS Group", "Shougang", "Anhui Conch Cement", "CNOOC", "Rosneft", "Lukoil", "Surgutneftegas",
        "Novatek", "Severstal", "NLMK", "Magnitogorsk Iron and Steel Works", "Evraz", "Rusal", "Nornickel", "SUEK", "ADNOC",
        "QatarEnergy", "Kuwait Petroleum Corporation", "Sonatrach", "Ecopetrol", "YPF", "ConocoPhillips", "Occidental Petroleum",
        "Marathon Petroleum", "Valero Energy", "Phillips 66", "Dow", "LyondellBasell", "United States Steel", "Nucor",
        "Cleveland-Cliffs", "Vistra", "American Electric Power", "Dominion Energy", "Berkshire Hathaway Energy", "Xcel Energy",
        "Tata Power", "Steel Authority of India", "Hindalco", "UltraTech Cement", "Reliance Industries", "Pertamina", "PTT",
        "Petronas", "Sasol", "Anglo American", "Teck Resources", "Peabody Energy", "Formosa Plastics", "China Steel",
        "Taipower", "Hyundai Steel", "ENEOS", "AGL Energy", "Woodside Energy", "Santos", "Fortescue", "Gerdau", "Ternium",
        "Salzgitter", "voestalpine", "SSAB", "OMV", "MOL Group", "Tauron", "Public Power Corporation", "Drax", "Buzzi"]

if __name__ == "__main__":
    names = sys.argv[1:]
    asyncio.run(main(MORE if names == ["--more"] else names or DEFAULT))
