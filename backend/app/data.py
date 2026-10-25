"""Emissions data: declared vs observed per country (data/countries.json) and
large emitting sites fetched on demand from Climate TRACE, cached on disk."""
import json
import time
from functools import lru_cache
from pathlib import Path

import httpx

from . import store

DATA = Path(__file__).resolve().parents[1] / "data"
SITES_DIR = DATA / "sites"
CARBON_PRICE = 72.0  # €/tCO2e, EU ETS order of magnitude (Oct 2026), shown as an assumption
SITE_YEAR = 2024
SITE_SECTORS = "power,manufacturing,fossil-fuel-operations,mineral-extraction,waste"

GROUP_LABELS = {"energy": "Energy & industry", "agriculture": "Agriculture", "waste": "Waste"}
SECTOR_LABELS = {
    "power": "Power", "transportation": "Transport", "buildings": "Buildings",
    "fossil-fuel-operations": "Oil, gas & coal", "manufacturing": "Manufacturing",
    "mineral-extraction": "Mining", "fluorinated-gases": "F-gases",
    "agriculture": "Agriculture", "waste": "Waste",
}


@lru_cache
def load() -> dict:
    return json.loads((DATA / "countries.json").read_text())


_findings: dict | None = None
_findings_at = 0.0


def invalidate() -> None:
    global _findings, _company_findings
    _findings = None
    _company_findings = None


def findings() -> dict:
    """Declarations found by research agents (store), cached for a few seconds."""
    global _findings, _findings_at
    if _findings is None or time.monotonic() - _findings_at > 10:
        try:
            _findings = store.all_findings()
        except Exception:
            _findings = _findings or {}
        _findings_at = time.monotonic()
    return _findings


_policies: dict | None = None
_policies_at = 0.0


def policies() -> dict:
    """Climate policy profiles (NDC, net zero, carbon pricing), cached for a few seconds."""
    global _policies, _policies_at
    if _policies is None or time.monotonic() - _policies_at > 15:
        try:
            _policies = store.policies()
        except Exception:
            _policies = _policies or {}
        _policies_at = time.monotonic()
    return _policies


def _from_finding(base: dict, f: dict) -> dict:
    o = f["observed"]
    return {"iso3": base["iso3"], "numeric": base["numeric"], "name": base["name"], "year": f["year"],
            "source": f"Found by agent: {f['document']}",
            "declared": {"total": f["total_mt"], "energy": f["energy_mt"], "agriculture": f["agriculture_mt"], "waste": f["waste_mt"]},
            "observed": {k: o[k] for k in ("total", "energy", "agriculture", "waste")},
            "observed_sectors": o.get("sectors") or base["observed_sectors"], "observed_latest": base["observed_latest"],
            "agent": {k: f.get(k) for k in ("document", "source_url", "source_title", "quote", "confidence", "notes", "verified", "updated_at")}}


_company_findings: dict | None = None
_company_at = 0.0


@lru_cache
def _companies_raw() -> dict:
    path = DATA / "companies.json"
    return json.loads(path.read_text()) if path.exists() else {"years": [], "companies": []}


def companies() -> list[dict]:
    """Largest companies: observed (Climate TRACE tracked assets) vs self-reported Scope 1 (research agents)."""
    global _company_findings, _company_at
    if _company_findings is None or time.monotonic() - _company_at > 10:
        try:
            _company_findings = store.company_findings()
        except Exception:
            _company_findings = _company_findings or {}
        _company_at = time.monotonic()
    raw = _companies_raw()
    latest = str(max(raw["years"])) if raw["years"] else "2024"
    try:
        profiles = store.company_profiles() if _company_findings is not None else {}
    except Exception:
        profiles = {}
    merged = {c["id"]: c for c in raw["companies"]}
    merged.update(profiles)  # companies discovered on demand override the static list
    out = []
    for c in merged.values():
        f = _company_findings.get(c["id"])
        site_total = sum(a["observed"] for a in c["assets"]) or 0
        shared = sum(a["observed"] for a in c["assets"] if a.get("shared_with")) / site_total if site_total else 0
        row = {**c, "observed_latest": c["observed"].get(latest), "observed_year": latest, "reported": None,
               "shared_share": round(shared, 2),
               "research": {"status": f["status"], "notes": f.get("notes")} if f else None}
        if f and f.get("status") == "found" and f["scope1_mt"] < max(c["observed"].values() or [0]) / 3:
            row["research"] = {"status": "implausible", "notes": f"Reported {f['scope1_mt']} Mt is far below the tracked sites: "
                               "likely a unit or scope error. Run the agent again."}
        elif f and f.get("status") == "found":
            year = str(f["year"]) if str(f["year"]) in c["observed"] else latest
            obs = c["observed"].get(year) or 0
            row["reported"] = {k: f.get(k) for k in ("year", "scope1_mt", "document", "source_url", "source_title",
                                                     "quote", "confidence", "verified")}
            if obs > 0:  # no tracked sites = nothing to compare with
                row["compare"] = {"year": int(year), "reported_year": f["year"], "observed": obs, "reported": f["scope1_mt"],
                                  "ratio": obs / f["scope1_mt"] if f["scope1_mt"] else None}
        out.append(row)
    return out


def find_company(query: str) -> dict | None:
    q = query.strip().lower()
    rows = companies()
    return next((c for c in rows if c["id"] == q or c["name"].lower() == q), None) or \
        next((c for c in rows if q in c["name"].lower() or any(q in s.lower() for s in c["subsidiaries"])), None)


@lru_cache
def market() -> dict:
    """EU ETS free allocation vs verified emissions per country (data/market.json)."""
    path = DATA / "market.json"
    return json.loads(path.read_text()) if path.exists() else {"year": None, "countries": {}}


def compared() -> dict:
    """Countries with a declaration: Climate Watch inventories, replaced by a newer one found by an agent, plus
    countries whose only declaration was found by an agent."""
    out = dict(load()["countries"])
    for iso, f in findings().items():
        if f.get("status") != "found" or not f.get("observed"):
            continue
        base = load()["undeclared"].get(iso) or load()["countries"].get(iso)
        if base and (iso not in out or (f.get("year") or 0) > out[iso]["year"]):
            out[iso] = _from_finding(base, f)
    return out


def undeclared() -> dict:
    found = compared()
    return {iso: c for iso, c in load()["undeclared"].items() if iso not in found}


def gap(c: dict) -> dict:
    d, o = c["declared"]["total"], c["observed"]["total"]
    g = o - d
    return {"declared": d, "observed": o, "gap": g, "gap_pct": g / d, "value_eur": g * 1e6 * CARBON_PRICE}


def summary(c: dict) -> dict:
    """Compact per-country record for the map."""
    if "declared" in c:
        return {"iso3": c["iso3"], "numeric": c["numeric"], "name": c["name"], "year": c["year"],
                "source": c["source"], **{k: round(v, 4) for k, v in gap(c).items()},
                "groups": {k: {"declared": c["declared"][k], "observed": c["observed"][k]} for k in GROUP_LABELS},
                "sectors": c["observed_sectors"], "observed_latest": c["observed_latest"], "agent": c.get("agent")}
    f = findings().get(c["iso3"])
    return {"research": {"status": f["status"], "notes": f.get("notes"), "updated_at": f.get("updated_at")} if f else None,
            "iso3": c["iso3"], "numeric": c["numeric"], "name": c["name"], "declared": None,
            "observed_latest": c["observed_latest"], "sectors": c["observed_sectors"]}


def all_countries() -> list[dict]:
    pol = policies()
    return [{**summary(c), "policy": pol.get(c["iso3"])} for c in (*compared().values(), *undeclared().values())]


def find(query: str) -> dict | None:
    """Country by ISO3 code or (partial) name."""
    q = query.strip().lower()
    pool = {**undeclared(), **compared()}
    if q.upper() in pool:
        return pool[q.upper()]
    for c in pool.values():
        if c["name"].lower() == q:
            return c
    for c in pool.values():
        if q in c["name"].lower():
            return c
    return None


def rank(metric: str = "gap", limit: int = 10, min_declared: float = 20) -> list[dict]:
    rows = [summary(c) for c in compared().values() if c["declared"]["total"] >= min_declared]
    key = {"gap": "gap", "gap_pct": "gap_pct", "declared": "declared", "observed": "observed"}.get(metric, "gap")
    rows.sort(key=lambda r: r[key], reverse=True)
    if metric == "over_declared":
        rows.sort(key=lambda r: r["gap_pct"])
    return rows[:limit]


def _site_kind(sector: str, asset_type: str) -> str:
    s = f"{sector} {asset_type}".lower()
    if "electricity" in s or "power" in s:
        return "power"
    if "steel" in s or "iron" in s:
        return "steel"
    if "cement" in s:
        return "cement"
    if "oil" in s or "gas" in s or "refin" in s:
        return "oil"
    if "coal" in s or "mining" in s or "ore" in s or "quarr" in s:
        return "mining"
    return "other"


def sites(iso3: str, limit: int = 25) -> list[dict]:
    """Largest observed sources in a country (Climate TRACE assets), cached on disk."""
    iso3 = iso3.upper()
    SITES_DIR.mkdir(parents=True, exist_ok=True)
    cache = SITES_DIR / f"{iso3}.json"
    if cache.exists():
        return json.loads(cache.read_text())[:limit]
    r = httpx.get("https://api.climatetrace.org/v6/assets", timeout=60,
                  params={"countries": iso3, "sectors": SITE_SECTORS, "year": SITE_YEAR, "limit": 1000})
    r.raise_for_status()
    out = []
    for a in r.json().get("assets") or []:
        em = sum((e.get("EmissionsQuantity") or 0) for e in a.get("EmissionsSummary") or [] if e.get("Gas") == "co2e_100yr")
        geo = (a.get("Centroid") or {}).get("Geometry")
        if em <= 0 or not geo:
            continue
        conf = None
        for block in a.get("Confidence") or []:
            if str(SITE_YEAR) in block:
                conf = (block[str(SITE_YEAR)][0] or {}).get("total_co2e_100yrgwp")
        owners = list(dict.fromkeys(o["CompanyName"].strip() for o in a.get("Owners") or [] if o.get("CompanyName")))
        out.append({"id": str(a["Id"]), "name": a["Name"], "owner": owners[0] if owners else None,
                    "kind": _site_kind(a.get("Sector", ""), a.get("AssetType") or ""),
                    "sector": a.get("Sector"), "type": a.get("AssetType"),
                    "observed": round(em / 1e6, 3), "confidence": conf, "coord": geo, "year": SITE_YEAR})
    out.sort(key=lambda s: s["observed"], reverse=True)
    out = out[:60]
    cache.write_text(json.dumps(out, ensure_ascii=False))
    return out[:limit]
