"""The Carbon Gap analyst: OpenAI Responses API with function calling and web search.

Data tools run on the server. Map tools are forwarded to the browser as
`action` events (the map moves while the model keeps talking)."""
import asyncio
import json
import os
from collections.abc import Iterator

from openai import OpenAI

from . import data, llm

MODEL = llm.MODEL
# Created even without a key so the app and its data views start; AI features then report a clear error.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "missing-key")

INSTRUCTIONS = f"""You are the analyst inside Carbon Gap, a tool for climate journalists and NGOs.
Carbon Gap compares what countries DECLARE to the UN (UNFCCC national inventories, total GHG excluding land use)
with what is OBSERVED by independent estimates (Climate TRACE, satellites + asset-level models, all sectors except
forestry), for the SAME year. The gap is valued at an assumed carbon price of €{data.CARBON_PRICE:.0f}/t.

Rules:
- Get every number from the data tools. Never invent figures. Units: MtCO2e.
- Whenever you talk about a place, move the map: select_country for one country, highlight_countries for several,
  focus_site for a site. Do this early, before writing your answer.
- A gap is a lead to investigate, never proof of fraud. Mention likely methodological causes when relevant
  (methane from fossil fuel operations, emission factors, sector coverage, reporting year, GWP version).
- For carbon markets, taxes, laws, targets (NDCs, net zero), reporting rules and how to read a gap, search the Carbon Gap
  knowledge base first (file_search). Use web_search for recent news or to confirm a fact that may have changed; cite it.
- Some declared figures were found by Carbon Gap research agents in recent UN reports (BTRs). Say so when you use
  them, and whether a person has verified the source (field "verified").
- Answer in the user's language, short: 2-5 sentences or a short list. No headings. Bold the key numbers.
- Company questions: get_companies (if unknown, discover_company), then show_company to put its sites on the globe. Observed company emissions only
  cover the sites Climate TRACE tracks; if they exceed the reported Scope 1, that is a lead (check boundaries, year).
- Carbon market questions (who must buy allowances, free allocation, surplus) about Europe: use get_market and show_market.
- Countries without a UN inventory since 2015 (e.g. China) only have observed emissions: say so.
"""

COUNTRY = {"type": "string", "description": "Country name or ISO3 code"}
KNOWLEDGE = data.DATA / "knowledge.json"
VECTOR_STORE = json.loads(KNOWLEDGE.read_text())["vector_store_id"] if KNOWLEDGE.exists() else None
TOOLS = [
    {"type": "web_search"},
    *([{"type": "file_search", "vector_store_ids": [VECTOR_STORE], "max_num_results": 4}] if VECTOR_STORE else []),
    {"type": "function", "name": "get_country", "strict": True,
     "description": "Declared vs observed emissions for one country, by sector group, plus metadata.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY}, "required": ["country"], "additionalProperties": False}},
    {"type": "function", "name": "rank_countries", "strict": True,
     "description": "Rank countries that have a recent UN inventory. gap = observed minus declared in Mt, gap_pct = relative gap, over_declared = observed below declared.",
     "parameters": {"type": "object", "properties": {
         "metric": {"type": "string", "enum": ["gap", "gap_pct", "over_declared", "declared", "observed"]},
         "limit": {"type": "integer", "description": "1-20"}},
         "required": ["metric", "limit"], "additionalProperties": False}},
    {"type": "function", "name": "get_sites", "strict": True,
     "description": "Largest observed emitting sites (power plants, steel, cement, oil & gas, mines) in a country, with owner and confidence.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY, "limit": {"type": "integer"}},
                    "required": ["country", "limit"], "additionalProperties": False}},
    {"type": "function", "name": "get_market", "strict": True,
     "description": "EU ETS carbon market position: verified emissions vs free allowances per country (latest year), the "
                    "shortfall its installations must buy, by sector. Pass an empty string for all countries ranked.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY}, "required": ["country"], "additionalProperties": False}},
    {"type": "function", "name": "launch_agents", "strict": True,
     "description": "Launch several research agents in parallel, visible on the globe, to find the missing UN declarations "
                    "of the largest emitters that have none yet. Use when the user asks to fill gaps or find missing data.",
     "parameters": {"type": "object", "properties": {"count": {"type": "integer", "description": "2-12, default 6"}},
                    "required": ["count"], "additionalProperties": False}},
    {"type": "function", "name": "show_market", "strict": True,
     "description": "Switch the globe to the carbon market view (EU ETS allowances: who must buy, who has surplus).",
     "parameters": {"type": "object", "properties": {"country": {"type": "string", "description": "Country to open, or empty"}},
                    "required": ["country"], "additionalProperties": False}},
    {"type": "function", "name": "get_companies", "strict": True,
     "description": "Largest emitting companies: observed emissions of their sites tracked by Climate TRACE vs the Scope 1 "
                    "they report themselves (found by research agents). Pass a company name, or an empty string for the ranking.",
     "parameters": {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"], "additionalProperties": False}},
    {"type": "function", "name": "show_company", "strict": True,
     "description": "Open a company on the globe (its tracked sites) and in the side panel. Empty string opens the company list.",
     "parameters": {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"], "additionalProperties": False}},
    {"type": "function", "name": "discover_company", "strict": True,
     "description": "Add ANY company not yet in Carbon Gap: profiles it with web search, finds its sites in Climate TRACE and "
                    "its reported Scope 1 (~30-60 s). Use when get_companies does not know the company.",
     "parameters": {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"], "additionalProperties": False}},
    {"type": "function", "name": "research_company", "strict": True,
     "description": "Launch a research agent that finds the company's self-reported Scope 1 emissions in its reports (~25 s).",
     "parameters": {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"], "additionalProperties": False}},
    {"type": "function", "name": "research_declaration", "strict": True,
     "description": "Launch a research agent that searches the web for the latest GHG inventory a country reported to the UN "
                    "(e.g. its Biennial Transparency Report) and adds it to Carbon Gap. Takes ~25 s. Use when a country has no declaration.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY}, "required": ["country"], "additionalProperties": False}},
    # map tools (executed in the browser)
    {"type": "function", "name": "select_country", "strict": True,
     "description": "Fly the globe to a country and open its sheet.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY}, "required": ["country"], "additionalProperties": False}},
    {"type": "function", "name": "highlight_countries", "strict": True,
     "description": "Outline and label several countries on the globe and fly to the first one.",
     "parameters": {"type": "object", "properties": {"countries": {"type": "array", "items": COUNTRY}},
                    "required": ["countries"], "additionalProperties": False}},
    {"type": "function", "name": "focus_site", "strict": True,
     "description": "Zoom the globe on one site returned by get_sites.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY, "site_id": {"type": "string"}},
                    "required": ["country", "site_id"], "additionalProperties": False}},
    {"type": "function", "name": "set_metric", "strict": True,
     "description": "Change what colours the globe.",
     "parameters": {"type": "object", "properties": {"metric": {"type": "string", "enum": ["gap", "declared", "observed"]}},
                    "required": ["metric"], "additionalProperties": False}},
    {"type": "function", "name": "open_report", "strict": True,
     "description": "Generate and open the full sourced report (dossier) for a country.",
     "parameters": {"type": "object", "properties": {"country": COUNTRY}, "required": ["country"], "additionalProperties": False}},
]
MAP_TOOLS = {"select_country", "highlight_countries", "focus_site", "set_metric", "open_report", "show_market", "show_company", "launch_agents"}


def _iso(name: str) -> str | None:
    c = data.find(name)
    return c["iso3"] if c else None


def _country_payload(c: dict) -> dict:
    out = _country_core(c)
    pol = data.policies().get(c["iso3"])
    if pol:
        out["climate_policy"] = {k: pol[k] for k in ("ndc_target", "net_zero_year", "net_zero_status", "carbon_pricing",
                                                    "paris_status", "latest_un_report")}
    return out


def _country_core(c: dict) -> dict:
    s = data.summary(c)
    if s.get("declared") is None:
        return {"country": c["name"], "iso3": c["iso3"], "note": "No UN inventory since 2015: observed only.",
                "observed_latest": c["observed_latest"], "observed_by_sector_Mt": c["observed_sectors"]}
    return {"country": c["name"], "iso3": c["iso3"], "inventory_year": c["year"], "declared_source": c["source"],
            "declared_Mt": round(s["declared"], 1), "observed_Mt": round(s["observed"], 1),
            "gap_Mt": round(s["gap"], 1), "gap_pct": round(s["gap_pct"] * 100, 1),
            "gap_value_eur": round(s["value_eur"]), "carbon_price_eur_per_t": data.CARBON_PRICE,
            "by_group": {data.GROUP_LABELS[k]: v for k, v in s["groups"].items()},
            "observed_by_sector_Mt": c["observed_sectors"], "observed_latest": c["observed_latest"],
            **({"declaration_found_by_research_agent": {k: c["agent"][k] for k in ("document", "source_url", "quote", "confidence", "verified")}}
               if c.get("agent") else {})}


def run_tool(name: str, args: dict) -> tuple[dict, dict | None]:
    """Returns (output for the model, action for the browser or None)."""
    if name == "get_country":
        c = data.find(args["country"])
        return (_country_payload(c) if c else {"error": f"Unknown country: {args['country']}"}), None
    if name == "rank_countries":
        rows = data.rank(args["metric"], max(1, min(20, args["limit"])))
        return {"metric": args["metric"], "rows": [
            {"country": r["name"], "iso3": r["iso3"], "year": r["year"], "declared_Mt": round(r["declared"], 1),
             "observed_Mt": round(r["observed"], 1), "gap_Mt": round(r["gap"], 1), "gap_pct": round(r["gap_pct"] * 100, 1)}
            for r in rows]}, None
    if name == "get_sites":
        iso = _iso(args["country"])
        if not iso:
            return {"error": f"Unknown country: {args['country']}"}, None
        rows = data.sites(iso, max(1, min(25, args["limit"])))
        return {"country": iso, "year": data.SITE_YEAR, "sites": [
            {k: s[k] for k in ("id", "name", "owner", "kind", "observed", "confidence")} for s in rows]}, None
    if name == "get_market":
        m = data.market()
        price = data.CARBON_PRICE
        if args["country"].strip():
            iso = _iso(args["country"])
            row = m["countries"].get(iso or "")
            if not row:
                return {"note": "Not covered by the EU ETS (EU, Norway, Iceland, Liechtenstein only)."}, None
            return {"year": m["year"], **{k: row[k] for k in ("name", "verified", "free", "shortfall", "sectors")},
                    "shortfall_value_eur": round(row["shortfall"] * 1e6 * price), "unit": "MtCO2e"}, None
        rows = sorted(m["countries"].values(), key=lambda r: -r["shortfall"])
        return {"year": m["year"], "unit": "MtCO2e", "carbon_price": price, "countries": [
            {k: r[k] for k in ("name", "verified", "free", "shortfall")} for r in rows]}, None
    if name == "launch_agents":
        n = max(2, min(12, args["count"] or 6))
        return {"ok": True, "note": f"{n} agents launched in the browser; results appear on the map in about a minute."}, {"name": name, "count": n}
    if name == "show_market":
        iso = _iso(args["country"]) if args["country"].strip() else None
        return {"ok": True}, {"name": name, "iso3": iso}
    if name == "get_companies":
        if args["company"].strip():
            c = data.find_company(args["company"])
            if not c:
                return {"error": "Company not in Carbon Gap's list of the 40 largest groups."}, None
            return {k: c.get(k) for k in ("id", "name", "observed", "observed_year", "reported", "compare", "countries",
                                          "asset_count", "subsidiaries")} | {
                "top_sites": [{k: a[k] for k in ("name", "country", "kind", "observed")} for a in c["assets"][:8]],
                "note": "Observed = sites tracked by Climate TRACE only (partial coverage, equal split between co-owners)."}, None
        return {"companies": [{"name": c["name"], "observed_Mt": c["observed_latest"], "reported_scope1_Mt": (c["reported"] or {}).get("scope1_mt"),
                               "ratio_observed_to_reported": round(c["compare"]["ratio"], 2) if c.get("compare") else None}
                              for c in data.companies()]}, None
    if name == "show_company":
        c = data.find_company(args["company"]) if args["company"].strip() else None
        return {"ok": True}, {"name": name, "company_id": c["id"] if c else None}
    if name == "discover_company":
        cid = asyncio.run(_discover(args["company"]))
        c = data.find_company(cid) if cid else None
        if not c:
            return {"error": f"Could not find emitting operations for {args['company']}."}, None
        return ({k: c.get(k) for k in ("name", "industry", "observed", "reported", "compare", "countries", "asset_count")},
                {"name": "refresh_companies", "company_id": c["id"]})
    if name == "research_company":
        c = data.find_company(args["company"])
        if not c:
            return {"error": "Unknown company"}, None
        f = asyncio.run(_research_company(c))
        return f, {"name": "refresh_companies", "company_id": c["id"]}
    if name == "research_declaration":
        iso = _iso(args["country"])
        if not iso:
            return {"error": "Unknown country"}, None
        f = asyncio.run(_research(iso))
        return f, {"name": "refresh_data", "iso3": iso}
    if name in ("select_country", "open_report"):
        iso = _iso(args["country"])
        return ({"ok": True}, {"name": name, "iso3": iso}) if iso else ({"error": "Unknown country"}, None)
    if name == "highlight_countries":
        isos = [i for i in (_iso(n) for n in args["countries"]) if i]
        return {"ok": True, "count": len(isos)}, {"name": name, "iso3s": isos}
    if name == "focus_site":
        return {"ok": True}, {"name": name, "iso3": _iso(args["country"]), "site_id": args["site_id"]}
    if name == "set_metric":
        return {"ok": True}, {"name": name, "metric": args["metric"]}
    return {"error": f"Unknown tool {name}"}, None


def chat(message: str, previous_response_id: str | None = None, context: dict | None = None) -> Iterator[dict]:
    """Stream events: delta, tool, action, sources, done, error."""
    text = message
    if context and context.get("selected"):
        text = f"[The user is looking at {context['selected']} on the map]\n{text}"
    if context and context.get("voice"):
        text = ("[Voice mode: your answer is read aloud. At most 2 short spoken sentences, under 45 words, no markdown, "
                "no lists, round numbers (\"about 750 million tonnes\"), mention at most 3 countries. Still move the map.]\n" + text)
    inputs: list = [{"role": "user", "content": text}]
    prev = previous_response_id
    for _ in range(8):  # tool rounds
        calls, response = [], None
        stream = client.responses.create(model=MODEL, instructions=INSTRUCTIONS, input=inputs, tools=TOOLS,
                                         previous_response_id=prev, reasoning={"effort": "low"}, stream=True)
        for ev in stream:
            if ev.type == "response.output_text.delta":
                yield {"type": "delta", "text": ev.delta}
            elif ev.type == "response.output_item.added" and ev.item.type == "web_search_call":
                yield {"type": "tool", "name": "web_search", "args": "searching the web"}
            elif ev.type == "response.output_item.added" and ev.item.type == "file_search_call":
                yield {"type": "tool", "name": "knowledge_base", "args": "reading the Carbon Gap knowledge base"}
            elif ev.type == "response.output_item.done" and ev.item.type == "function_call":
                calls.append(ev.item)
            elif ev.type == "response.completed":
                response = ev.response
            elif ev.type in ("response.failed", "error"):
                yield {"type": "error", "message": "The model could not answer. Try again."}
                return
        if response is None:
            yield {"type": "error", "message": "The answer was cut off. Try again."}
            return
        prev = response.id
        if not calls:
            yield {"type": "sources", "items": _citations(response)}
            yield {"type": "done", "response_id": response.id}
            return
        inputs = []
        for call in calls:
            args = json.loads(call.arguments or "{}")
            output, action = run_tool(call.name, args)
            yield {"type": "tool", "name": call.name, "args": _short(args)}
            if action:
                yield {"type": "action", **action}
            inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(output)})
    yield {"type": "error", "message": "Too many steps. Ask a narrower question."}


async def _research(iso: str) -> dict:
    from . import research
    last = {}
    async for ev in research.research(iso):
        last = ev
    f = last.get("finding") or {"status": "error", "notes": last.get("message")}
    return {k: v for k, v in f.items() if k != "observed"} | {"observed_same_year": (f.get("observed") or {}).get("total")}


async def _discover(name: str) -> str | None:
    from . import discover
    cid = None
    async for ev in discover.discover(name):
        cid = ev.get("company_id", cid)
    return cid


async def _research_company(c: dict) -> dict:
    from . import research
    last = {}
    async for ev in research.research_company(c):
        last = ev
    return last.get("finding") or {"status": "error", "notes": last.get("message")}


def _short(args: dict) -> str:
    return ", ".join(", ".join(v) if isinstance(v, list) else str(v) for v in args.values())


def _citations(response) -> list[dict]:
    seen, out = set(), []
    for item in response.output:
        for part in getattr(item, "content", None) or []:
            for a in getattr(part, "annotations", None) or []:
                if getattr(a, "type", "") == "url_citation" and a.url not in seen:
                    seen.add(a.url)
                    out.append({"title": a.title or a.url, "url": a.url})
    return out
