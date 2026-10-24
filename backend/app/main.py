"""Carbon Gap API. For now it serves the clickable mockup and a health check."""
from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

app = FastAPI(title="Carbon Gap")


@app.get("/api/health")
def health():
    return {"ok": True, "openai": bool(os.getenv("OPENAI_API_KEY"))}


app.mount("/", StaticFiles(directory=ROOT / "mockup", html=True), name="mockup")
