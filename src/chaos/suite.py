"""Run every fault against a clean day, record whether it was caught, and write small files for the Streamlit monitor."""
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .faults import EXPECTED_CATCH, inject
from .generator import generate_day
from .pipeline import connect, run_day


def run_suite(out_dir: Path, start: date = date(2026, 11, 1), clean_days: int = 10, seed: int = 7) -> dict:
    work = Path(tempfile.mkdtemp())
    incoming, db = work / "incoming", work / "chaos.duckdb"
    con = connect(db)
    for i in range(clean_days):
        generate_day(start + timedelta(days=i), incoming, seed)
        run_day(start + timedelta(days=i), incoming, con)

    fault_day = start + timedelta(days=clean_days)
    rows = []
    for fault, expected in EXPECTED_CATCH.items():
        generate_day(fault_day, incoming, seed)
        inject(fault, incoming, fault_day)
        res = run_day(fault_day, incoming, con)
        ms = con.execute("SELECT detect_ms FROM run_log ORDER BY finished_at DESC LIMIT 1").fetchone()[0]
        rows.append({"fault": fault, "expected_rule": expected, "caught_by": res["caught_by"],
                     "caught": res["status"] != "loaded", "correct_rule": res["caught_by"] == expected,
                     "detect_ms": round(ms, 1)})
        generate_day(fault_day, incoming, seed)       # the source resends a clean file
        run_day(fault_day, incoming, con)             # the rerun replaces the day: a safe, idempotent backfill

    faults = pd.DataFrame(rows)
    runs = con.execute("SELECT load_date, status, rows_in, rows_loaded, caught_by, round(detect_ms,1) AS detect_ms "
                       "FROM run_log ORDER BY started_at").df()
    per_day = con.execute("SELECT load_date, count(*) AS rows, round(sum(amount),2) AS amount FROM orders GROUP BY 1 ORDER BY 1").df()
    duplicates = con.execute("SELECT count(*) FROM (SELECT order_id FROM orders GROUP BY 1 HAVING count(*) > 1)").fetchone()[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    faults.to_parquet(out_dir / "faults.parquet", index=False)
    runs.to_parquet(out_dir / "runs.parquet", index=False)
    per_day.to_parquet(out_dir / "per_day.parquet", index=False)
    summary = {"faults_injected": len(faults), "faults_caught": int(faults.caught.sum()),
               "caught_by_expected_rule": int(faults.correct_rule.sum()), "duplicate_order_ids_after_reruns": int(duplicates)}
    pd.DataFrame([summary]).to_parquet(out_dir / "summary.parquet", index=False)
    con.close()
    shutil.rmtree(work, ignore_errors=True)
    return summary
