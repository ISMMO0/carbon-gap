"""Country dossiers written by the model with Structured Outputs, plus a spoken briefing (TTS)."""
import json
from pathlib import Path

from . import data
from .agent import MODEL, _country_payload, client

REPORTS = data.DATA / "reports"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["headline", "summary", "findings", "sectors", "sites_to_investigate", "next_steps", "caveats", "briefing"],
    "properties": {
        "headline": {"type": "string", "description": "One factual sentence, max 14 words."},
        "summary": {"type": "string", "description": "Two short paragraphs separated by a blank line. Numbers in MtCO2e."},
        "findings": {"type": "array", "items": {"type": "string"}, "description": "3-4 key findings."},
        "sectors": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["group", "note"],
            "properties": {"group": {"type": "string"}, "note": {"type": "string"}}}},
        "sites_to_investigate": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "owner", "why"],
            "properties": {"name": {"type": "string"}, "owner": {"type": "string"}, "why": {"type": "string"}}}},
        "next_steps": {"type": "array", "items": {"type": "string"}, "description": "3 concrete steps for a journalist or NGO."},
        "caveats": {"type": "array", "items": {"type": "string"}, "description": "Methodological limits, 2-3 items."},
        "briefing": {"type": "string", "description": "A 45-second spoken briefing of the dossier, plain sentences, no lists."},
    },
}

PROMPT = """Write an investigation dossier on the emissions gap of {name} for climate journalists and NGOs.
Use ONLY the data below for numbers. Use web search for recent context (policy, incidents, energy mix) and keep it brief.
A gap is a lead to investigate, never proof of misreporting. Explain plausible methodological causes.
Sites: pick 3-5 from the list, explain why each matters.

DATA (MtCO2e):
{payload}

LARGEST OBSERVED SITES ({site_year}):
{sites}"""


def build(iso3: str, refresh: bool = False) -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{iso3}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    c = data.find(iso3)
    if not c:
        raise KeyError(iso3)
    sites = data.sites(c["iso3"], 12)
    payload = _country_payload(c)
    resp = client.responses.create(
        model=MODEL, reasoning={"effort": "low"}, tools=[{"type": "web_search"}],
        input=PROMPT.format(name=c["name"], payload=json.dumps(payload, indent=1), site_year=data.SITE_YEAR,
                            sites="\n".join(f"- {s['name']} ({s['owner'] or 'owner unknown'}, {s['kind']}): {s['observed']} Mt, confidence {s['confidence']}" for s in sites)),
        text={"format": {"type": "json_schema", "name": "dossier", "strict": True, "schema": SCHEMA}},
    )
    report = json.loads(resp.output_text)
    report["sources"] = [{"title": a.title or a.url, "url": a.url}
                         for item in resp.output for part in getattr(item, "content", None) or []
                         for a in getattr(part, "annotations", None) or [] if getattr(a, "type", "") == "url_citation"]
    report["data"] = payload
    report["sites"] = sites[:8]
    report["iso3"] = c["iso3"]
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


def briefing_audio(iso3: str) -> Path:
    path = REPORTS / f"{iso3}.mp3"
    if path.exists():
        return path
    report = build(iso3)
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts", voice="sage", input=report["briefing"],
        instructions="Calm, confident documentary narrator. Clear diction, natural pauses.", response_format="mp3",
    ) as r:
        r.stream_to_file(path)
    return path
