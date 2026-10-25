"""Carbon Gap API + static front-end."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, data, discover, report, research, store, voice  # noqa: E402

app = FastAPI(title="Carbon Gap")


@app.middleware("http")
async def no_stale_frontend(request, call_next):
    """The front-end changes often during the hackathon: never let browsers serve an old copy."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health():
    return {"ok": True, "openai": bool(os.getenv("OPENAI_API_KEY")), "countries": len(data.compared()),
            "store": store.backend(), "findings": len(data.findings())}


@app.get("/api/countries")
def countries():
    return {"carbon_price": data.CARBON_PRICE, "group_labels": data.GROUP_LABELS,
            "sector_labels": data.SECTOR_LABELS, "countries": data.all_countries()}


@app.get("/api/companies")
def companies():
    return {"carbon_price": data.CARBON_PRICE, "companies": data.companies()}


class DiscoverIn(BaseModel):
    name: str


@app.post("/api/companies/discover")
async def discover_company(body: DiscoverIn):
    """Find any company: profile (OpenAI web search), Climate TRACE sites, reported Scope 1. Streams steps."""
    async def events():
        try:
            async for ev in discover.discover(body.name.strip()[:120]):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Discovery failed: {type(e).__name__}'})}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/companies/{company_id}/research")
async def research_company(company_id: str):
    c = data.find_company(company_id)
    if not c:
        raise HTTPException(404, "Unknown company.")

    async def events():
        try:
            async for ev in research.research_company(c):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Research failed: {type(e).__name__}'})}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/market")
def market():
    m = data.market()
    return {**m, "carbon_price": data.CARBON_PRICE}


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


class VerifyIn(BaseModel):
    verified: bool


@app.post("/api/research/{iso3}/verify")
def verify(iso3: str, body: VerifyIn):
    """A person confirms (or un-confirms) a figure found by a research agent."""
    if not store.set_verified(iso3.upper(), body.verified):
        raise HTTPException(404, "No finding for this country.")
    data.invalidate()
    return {"ok": True}


@app.get("/api/research")
def list_research():
    return {"store": store.backend(), "findings": list(data.findings().values())}


class ChatIn(BaseModel):
    message: str
    previous_response_id: str | None = None
    selected: str | None = None
    voice: bool = False


@app.post("/api/chat")
def chat(body: ChatIn):
    def events():
        try:
            for ev in agent.chat(body.message, body.previous_response_id, {"selected": body.selected, "voice": body.voice}):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # surface a readable error to the UI
            yield f"data: {json.dumps({'type': 'error', 'message': f'Analyst error: {type(e).__name__}'})}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    blob = await audio.read()
    if len(blob) < 1200:
        return {"text": ""}
    try:
        return {"text": await run_in_threadpool(voice.transcribe, blob, audio.filename or "speech.webm")}
    except Exception:
        raise HTTPException(502, "Transcription failed.")


class SpeakIn(BaseModel):
    text: str


@app.post("/api/speak")
def speak(body: SpeakIn):
    return StreamingResponse(voice.speak(body.text[:1500]), media_type="audio/mpeg")


@app.get("/api/speak")
def speak_get(text: str):
    """GET variant so an <audio> element can stream the answer as it is generated."""
    return StreamingResponse(voice.speak(text[:1500]), media_type="audio/mpeg")


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
