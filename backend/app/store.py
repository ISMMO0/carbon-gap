"""Storage for research findings: Postgres (DATABASE_URL) with a local JSON fallback
so the app keeps working when the database is unreachable."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
FALLBACK = DATA / "findings.json"

SCHEMA = """
create table if not exists findings (
  iso3 text primary key,
  status text not null,               -- found | not_found | error
  year int,
  total_mt double precision,
  energy_mt double precision,
  agriculture_mt double precision,
  waste_mt double precision,
  observed jsonb,                     -- Climate TRACE for the same year
  document text,
  source_url text,
  source_title text,
  quote text,
  confidence text,
  notes text,
  verified boolean not null default false,
  updated_at timestamptz not null default now()
);
"""
COMPANY_SCHEMA = """
create table if not exists company_findings (
  key text primary key,               -- company id (slug)
  status text not null,               -- found | not_found | error
  year int,
  scope1_mt double precision,
  document text,
  source_url text,
  source_title text,
  quote text,
  confidence text,
  notes text,
  verified boolean not null default false,
  updated_at timestamptz not null default now()
);
"""
COMPANY_COLS = ["key", "status", "year", "scope1_mt", "document", "source_url", "source_title", "quote", "confidence",
                "notes", "verified", "updated_at"]
COMPANY_FALLBACK = DATA / "company_findings.json"

COLS = ["iso3", "status", "year", "total_mt", "energy_mt", "agriculture_mt", "waste_mt", "observed", "document",
        "source_url", "source_title", "quote", "confidence", "notes", "verified", "updated_at"]

_lock = threading.Lock()
_pg_ok: bool | None = None


def _pg():
    import psycopg
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=8, autocommit=True)


def backend() -> str:
    """'postgres' when the database answers, else 'file'. Checked once per process."""
    global _pg_ok
    if _pg_ok is None:
        try:
            with _pg() as c:
                c.execute(SCHEMA)
                c.execute(COMPANY_SCHEMA)
            _pg_ok = True
        except Exception:
            _pg_ok = False
    return "postgres" if _pg_ok else "file"


def save(f: dict) -> None:
    f = {**{k: None for k in COLS}, **f, "verified": bool(f.get("verified")),
         "updated_at": datetime.now(timezone.utc).isoformat()}
    if backend() == "postgres":
        from psycopg.types.json import Jsonb
        vals = [Jsonb(f[k]) if k == "observed" else f[k] for k in COLS]
        sets = ", ".join(f"{k} = excluded.{k}" for k in COLS[1:])
        try:
            with _pg() as c:
                c.execute(f"insert into findings ({', '.join(COLS)}) values ({', '.join(['%s'] * len(COLS))}) "
                          f"on conflict (iso3) do update set {sets}", vals)
            return
        except Exception:
            pass  # database unreachable: keep the finding locally
    with _lock:
        rows = _read_file()
        rows[f["iso3"]] = f
        FALLBACK.write_text(json.dumps(rows, ensure_ascii=False, indent=1))


def all_findings() -> dict[str, dict]:
    if backend() == "postgres":
        from psycopg.rows import dict_row
        try:
            with _pg() as c, c.cursor(row_factory=dict_row) as cur:
                rows = cur.execute("select * from findings").fetchall()
            return {**_read_file(), **{r["iso3"]: {**r, "updated_at": r["updated_at"].isoformat()} for r in rows}}
        except Exception:
            pass
    with _lock:
        return _read_file()


def _read_file() -> dict:
    return json.loads(FALLBACK.read_text()) if FALLBACK.exists() else {}


def migrate_file_to_postgres() -> int:
    """Copy locally kept findings into Postgres once it is reachable."""
    rows = _read_file()
    if backend() != "postgres":
        return 0
    for f in rows.values():
        save(f)
    return len(rows)


def set_verified(iso3: str, verified: bool) -> bool:
    rows = all_findings()
    if iso3 not in rows:
        return False
    save({**rows[iso3], "verified": verified})
    return True


def save_company(f: dict) -> None:
    f = {**{k: None for k in COMPANY_COLS}, **f, "verified": bool(f.get("verified")),
         "updated_at": datetime.now(timezone.utc).isoformat()}
    if backend() == "postgres":
        sets = ", ".join(f"{k} = excluded.{k}" for k in COMPANY_COLS[1:])
        try:
            with _pg() as c:
                c.execute(f"insert into company_findings ({', '.join(COMPANY_COLS)}) values "
                          f"({', '.join(['%s'] * len(COMPANY_COLS))}) on conflict (key) do update set {sets}",
                          [f[k] for k in COMPANY_COLS])
            return
        except Exception:
            pass
    with _lock:
        rows = json.loads(COMPANY_FALLBACK.read_text()) if COMPANY_FALLBACK.exists() else {}
        rows[f["key"]] = f
        COMPANY_FALLBACK.write_text(json.dumps(rows, ensure_ascii=False, indent=1))


def company_findings() -> dict[str, dict]:
    local = json.loads(COMPANY_FALLBACK.read_text()) if COMPANY_FALLBACK.exists() else {}
    if backend() == "postgres":
        from psycopg.rows import dict_row
        try:
            with _pg() as c, c.cursor(row_factory=dict_row) as cur:
                rows = cur.execute("select * from company_findings").fetchall()
            return {**local, **{r["key"]: {**r, "updated_at": r["updated_at"].isoformat()} for r in rows}}
        except Exception:
            pass
    return local
