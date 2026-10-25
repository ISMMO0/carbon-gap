"""Climate policy profile of a country: NDC target, net-zero year, carbon pricing, latest UN report.

Researched with OpenAI (Responses API + web_search + Structured Outputs), stored in Postgres (country_policies)."""
import json

from . import data, llm, store

MODEL = llm.MODEL

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["ndc_target", "ndc_year", "net_zero_year", "net_zero_status", "carbon_pricing", "paris_status",
                 "latest_un_report", "notes", "sources"],
    "properties": {
        "ndc_target": {"type": "string", "description": "Current NDC headline target in one short sentence, e.g. '-55% net GHG by 2030 vs 1990'."},
        "ndc_year": {"type": ["integer", "null"], "description": "Target year of that NDC headline (e.g. 2030 or 2035)."},
        "net_zero_year": {"type": ["integer", "null"], "description": "Net-zero or carbon-neutrality target year, null if none."},
        "net_zero_status": {"type": "string", "enum": ["in law", "policy document", "pledge", "none"]},
        "carbon_pricing": {"type": "array", "description": "Carbon taxes and emissions trading systems in force (max 4).",
                           "items": {"type": "object", "additionalProperties": False, "required": ["name", "type", "price"],
                                     "properties": {"name": {"type": "string"},
                                                    "type": {"type": "string", "enum": ["ETS", "tax"]},
                                                    "price": {"type": "string", "description": "Recent price with currency and year, or 'n/a'."}}}},
        "paris_status": {"type": "string", "description": "e.g. 'Party', 'Signed, not ratified', 'Withdrawing'."},
        "latest_un_report": {"type": "string", "description": "Latest transparency report submitted to the UNFCCC, with year (e.g. 'BTR1, Dec 2024')."},
        "notes": {"type": "string", "description": "One sentence of context useful to a journalist."},
        "sources": {"type": "array", "items": {"type": "string"}, "description": "URLs used (max 4)."},
    },
}


async def research_policy(iso3: str) -> dict | None:
    c = data.find(iso3)
    if not c:
        return None
    resp = await llm.respond(
        model=MODEL, reasoning={"effort": "low"}, tools=[{"type": "web_search"}],
        input=f"Climate policy profile of {c['name']} as of 2026: current NDC headline target, net-zero target year and its "
              f"legal status, carbon taxes and emissions trading systems in force with recent prices, Paris Agreement status, "
              f"and the latest transparency report it submitted to the UNFCCC. Use web search and official sources. "
              f"Be factual; use null or 'none' when there is nothing.",
        text={"format": {"type": "json_schema", "name": "policy", "strict": True, "schema": SCHEMA}})
    profile = {"iso3": c["iso3"], **json.loads(resp.output_text)}
    store.save_policy(profile)
    return profile
