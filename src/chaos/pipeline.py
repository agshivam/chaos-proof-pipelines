"""The pipeline for one day: freshness, contract, reconciliation, then an idempotent load. Every run is logged."""
import json
import shutil
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd

from .alerts import alert
from .contract import load_contract, validate

ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACT = ROOT / "contracts" / "orders.yaml"


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id VARCHAR, customer_id VARCHAR, order_ts TIMESTAMP, amount DOUBLE,
            currency VARCHAR, status VARCHAR, load_date DATE)""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            run_id VARCHAR, load_date DATE, started_at TIMESTAMP, finished_at TIMESTAMP, status VARCHAR,
            rows_in INTEGER, rows_loaded INTEGER, caught_by VARCHAR, detail VARCHAR, detect_ms DOUBLE)""")
    return con


def _log(con, run_id, day, started, status, rows_in, rows_loaded, caught_by, detail, t0):
    ms = (time.perf_counter() - t0) * 1000
    con.execute("INSERT INTO run_log VALUES (?,?,?,?,?,?,?,?,?,?)",
                [run_id, day, started, datetime.now(timezone.utc).replace(tzinfo=None), status,
                 rows_in, rows_loaded, caught_by, detail, ms])


def run_day(day: date, incoming: Path, con: duckdb.DuckDBPyConnection, quarantine: Path | None = None) -> dict:
    """Process one day. Returns {status, caught_by, detail}. status is loaded, rejected or failed."""
    contract = load_contract(CONTRACT)
    run_id, t0 = str(uuid.uuid4())[:8], time.perf_counter()
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    f = incoming / f"orders_{day:%Y-%m-%d}.csv"
    m = incoming / f"manifest_{day:%Y-%m-%d}.json"

    # 1. Freshness: the file and its control totals must exist.
    if not f.exists() or not m.exists():
        detail = f"no source file for {day}"
        _log(con, run_id, day, started, "failed", 0, 0, "freshness", detail, t0)
        alert(f"[orders {day}] FAILED freshness: {detail}")
        return {"status": "failed", "caught_by": "freshness", "detail": detail}

    df = pd.read_csv(f, dtype=str, keep_default_na=False)
    manifest = json.loads(m.read_text())

    # 2. Contract: schema, nulls, types, ranges, categories, uniqueness, volume.
    violations = validate(df, contract)
    if violations:
        first = violations[0]
        detail = json.dumps([v.to_dict() for v in violations])
        if quarantine:
            quarantine.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, quarantine / f.name)
        _log(con, run_id, day, started, "rejected", len(df), 0, first.rule, detail, t0)
        alert(f"[orders {day}] REJECTED by contract rule '{first.rule}' on {first.column}: {first.detail}")
        return {"status": "rejected", "caught_by": first.rule, "detail": detail}

    # 3. Reconciliation: what we hold must equal what the source says it sent.
    tol = contract["reconciliation"]["amount_tolerance"]
    amount_sum = round(float(pd.to_numeric(df["amount"]).sum()), 2)
    if len(df) != manifest["row_count"] or abs(amount_sum - manifest["amount_sum"]) > tol:
        detail = (f"rows {len(df)} vs source {manifest['row_count']}, "
                  f"amount {amount_sum} vs source {manifest['amount_sum']}")
        if quarantine:
            quarantine.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, quarantine / f.name)
        _log(con, run_id, day, started, "rejected", len(df), 0, "reconciliation", detail, t0)
        alert(f"[orders {day}] REJECTED by reconciliation: {detail}")
        return {"status": "rejected", "caught_by": "reconciliation", "detail": detail}

    # 4. Idempotent load: replace the day's partition inside one transaction, so a rerun never duplicates rows.
    out = df.copy()
    out["order_ts"] = pd.to_datetime(out["order_ts"])
    out["amount"] = pd.to_numeric(out["amount"])
    out["load_date"] = day
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM orders WHERE load_date = ?", [day])
        con.execute("INSERT INTO orders SELECT order_id, customer_id, order_ts, amount, currency, status, load_date FROM out")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    _log(con, run_id, day, started, "loaded", len(df), len(df), None, "", t0)
    return {"status": "loaded", "caught_by": None, "detail": ""}


def backfill(start: date, end: date, incoming: Path, con, quarantine: Path | None = None) -> list[dict]:
    """Run every day from start to end inclusive. Safe to repeat: each day replaces its own partition."""
    results, d = [], start
    while d <= end:
        results.append({"date": d, **run_day(d, incoming, con, quarantine)})
        d += timedelta(days=1)
    return results
