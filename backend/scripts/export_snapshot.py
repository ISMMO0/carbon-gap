"""Save the research agents' results (from Postgres) into data/snapshot.json, committed with the repo,
so a fresh clone without a database shows the same data.

Run: .venv/bin/python -m scripts.export_snapshot
"""
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import store  # noqa: E402

if __name__ == "__main__":
    snap = {"findings": store.all_findings(), "company_findings": store.company_findings(),
            "company_profiles": store.company_profiles()}
    store.SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, default=str))
    print({k: len(v) for k, v in snap.items()}, "→", store.SNAPSHOT)
