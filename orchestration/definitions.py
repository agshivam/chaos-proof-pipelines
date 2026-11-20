"""Dagster definitions: one asset per day-partition, a daily schedule and a backfill-friendly partition set.

Run the UI:  dagster dev -f orchestration/definitions.py
Each partition is one day. Backfilling a range in the UI re-runs those days, and because the load replaces a day's
partition, a backfill is always safe to repeat.
"""
import sys
from datetime import date
from pathlib import Path

import dagster as dg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from chaos.generator import generate_day  # noqa: E402
from chaos.pipeline import connect, run_day  # noqa: E402

DATA = ROOT / "data"
daily = dg.DailyPartitionsDefinition(start_date="2026-11-01")


@dg.asset(partitions_def=daily, description="Pretend source system: writes the day's orders file and its control totals.")
def source_orders_file(context: dg.AssetExecutionContext) -> None:
    day = date.fromisoformat(context.partition_key)
    generate_day(day, DATA / "incoming")
    context.log.info(f"wrote source file for {day}")


@dg.asset(partitions_def=daily, deps=[source_orders_file],
          description="Validate against the contract, reconcile with control totals, then load idempotently.")
def orders(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    day = date.fromisoformat(context.partition_key)
    con = connect(DATA / "chaos.duckdb")
    result = run_day(day, DATA / "incoming", con, DATA / "quarantine")
    con.close()
    if result["status"] != "loaded":
        raise dg.Failure(description=f"{result['caught_by']}: {result['detail'][:300]}")
    return dg.MaterializeResult(metadata={"status": result["status"]})


daily_job = dg.define_asset_job("daily_orders", selection=[source_orders_file, orders], partitions_def=daily)
daily_schedule = dg.build_schedule_from_partitioned_job(daily_job, hour_of_day=2)

defs = dg.Definitions(assets=[source_orders_file, orders], jobs=[daily_job], schedules=[daily_schedule])
