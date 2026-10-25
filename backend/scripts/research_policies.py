"""Research the climate policy profile of the largest emitting countries, in parallel (OpenAI web search).

Run: .venv/bin/python -m scripts.research_policies [N] [CONCURRENCY]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import data, policy, store  # noqa: E402


async def main(n, conc):
    done = store.policies()
    rows = sorted(data.all_countries(), key=lambda c: -((c.get("observed") if c.get("declared") else None)
                                                         or (c.get("observed_latest") or {}).get("total") or 0))
    todo = [c for c in rows if c["iso3"] not in done][:n]
    sem = asyncio.Semaphore(conc)

    async def one(c):
        async with sem:
            try:
                p = await policy.research_policy(c["iso3"])
                print(f"[{c['iso3']}] net zero {p['net_zero_year']} · {len(p['carbon_pricing'])} carbon price(s) · {p['ndc_target'][:70]}", flush=True)
            except Exception as e:
                print(f"[{c['iso3']}] failed: {type(e).__name__}", flush=True)
    await asyncio.gather(*(one(c) for c in todo))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    conc = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    asyncio.run(main(n, conc))
