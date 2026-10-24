"""Upload knowledge/*.md to an OpenAI vector store used by the analyst's file_search tool.

Run: .venv/bin/python -m scripts.sync_knowledge   (re-run after editing the knowledge files)
The vector store id is saved in data/knowledge.json.
"""
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")
STATE = ROOT / "backend" / "data" / "knowledge.json"


def main():
    client = OpenAI()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get("vector_store_id"):  # replace the old store so edits are picked up
        try:
            client.vector_stores.delete(state["vector_store_id"])
        except Exception:
            pass
    vs = client.vector_stores.create(name="carbon-gap-knowledge")
    for md in sorted((ROOT / "knowledge").glob("*.md")):
        with md.open("rb") as f:
            res = client.vector_stores.files.upload_and_poll(vector_store_id=vs.id, file=f)
        print(md.name, res.status)
    STATE.write_text(json.dumps({"vector_store_id": vs.id}, indent=1))
    print("vector store", vs.id)


if __name__ == "__main__":
    main()
