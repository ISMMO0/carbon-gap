"""Carbon Gap API + static front-end."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, data, report, research, store  # noqa: E402

app = FastAPI(title="Carbon Gap")


@app.get("/api/health")
def health():
    return {"ok": True, "openai": bool(os.getenv("OPENAI_API_KEY")), "countries": len(data.compared()),
            "store": store.backend(), "findings": len(data.findings())}


@app.get("/api/countries")
def countries():
    return {"carbon_price": data.CARBON_PRICE, "group_labels": data.GROUP_LABELS,
            "sector_labels": data.SECTOR_LABELS, "countries": data.all_countries()}


@app.get("/api/countries/{iso3}/sites")
async def sites(iso3: str, limit: int = 25):
    try:
        return {"year": data.SITE_YEAR, "sites": await run_in_threadpool(data.sites, iso3, limit)}
    except Exception:
        raise HTTPException(502, "Site data is unavailable right now.")


@app.post("/api/research/{iso3}")
async def run_research(iso3: str):
    """Run a research agent live; streams its steps as SSE."""
    async def events():
        try:
            async for ev in research.research(iso3.upper()):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Research failed: {type(e).__name__}'})}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/research")
def list_research():
    return {"store": store.backend(), "findings": list(data.findings().values())}


class ChatIn(BaseModel):
    message: str
    previous_response_id: str | None = None
    selected: str | None = None


@app.post("/api/chat")
def chat(body: ChatIn):
    def events():
        try:
            for ev in agent.chat(body.message, body.previous_response_id, {"selected": body.selected}):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # surface a readable error to the UI
            yield f"data: {json.dumps({'type': 'error', 'message': f'Analyst error: {type(e).__name__}'})}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/report/{iso3}")
async def make_report(iso3: str, refresh: bool = False):
    try:
        return await run_in_threadpool(report.build, iso3.upper(), refresh)
    except KeyError:
        raise HTTPException(404, "Unknown country.")


@app.get("/api/report/{iso3}/audio")
async def report_audio(iso3: str):
    try:
        return FileResponse(await run_in_threadpool(report.briefing_audio, iso3.upper()), media_type="audio/mpeg")
    except KeyError:
        raise HTTPException(404, "Unknown country.")


app.mount("/mockup", StaticFiles(directory=ROOT / "mockup", html=True), name="mockup")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
