import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from chaos.faults import EXPECTED_CATCH, inject  # noqa: E402
from chaos.generator import generate_day  # noqa: E402
from chaos.pipeline import backfill, connect, run_day  # noqa: E402

DAY = date(2026, 11, 1)


@pytest.fixture
def env(tmp_path):
    incoming = tmp_path / "in"
    return incoming, connect(tmp_path / "t.duckdb"), tmp_path / "q"


def test_clean_day_loads(env):
    incoming, con, q = env
    generate_day(DAY, incoming)
    assert run_day(DAY, incoming, con, q)["status"] == "loaded"
    assert con.execute("SELECT count(*) FROM orders").fetchone()[0] > 0


@pytest.mark.parametrize("fault,rule", list(EXPECTED_CATCH.items()))
def test_every_fault_is_caught_by_the_expected_rule(env, fault, rule):
    incoming, con, q = env
    generate_day(DAY, incoming)
    inject(fault, incoming, DAY)
    res = run_day(DAY, incoming, con, q)
    assert res["status"] != "loaded"
    assert res["caught_by"] == rule
    assert con.execute("SELECT count(*) FROM orders").fetchone()[0] == 0   # nothing bad was loaded


def test_rejected_file_is_quarantined(env):
    incoming, con, q = env
    generate_day(DAY, incoming)
    inject("bad_category", incoming, DAY)
    run_day(DAY, incoming, con, q)
    assert (q / f"orders_{DAY}.csv").exists()


def test_rerun_is_idempotent(env):
    incoming, con, q = env
    generate_day(DAY, incoming)
    run_day(DAY, incoming, con, q)
    first = con.execute("SELECT count(*), sum(amount) FROM orders").fetchone()
    run_day(DAY, incoming, con, q)
    run_day(DAY, incoming, con, q)
    assert con.execute("SELECT count(*), sum(amount) FROM orders").fetchone() == first


def test_backfill_range_twice_gives_same_counts(env):
    incoming, con, q = env
    for i in range(5):
        generate_day(DAY + timedelta(days=i), incoming)
    backfill(DAY, DAY + timedelta(days=4), incoming, con, q)
    first = con.execute("SELECT count(*), sum(amount) FROM orders").fetchone()
    backfill(DAY, DAY + timedelta(days=4), incoming, con, q)
    assert con.execute("SELECT count(*), sum(amount) FROM orders").fetchone() == first


def test_late_file_recovers_on_backfill(env):
    incoming, con, q = env
    assert run_day(DAY, incoming, con, q)["caught_by"] == "freshness"
    generate_day(DAY, incoming)                      # the file finally arrives
    assert run_day(DAY, incoming, con, q)["status"] == "loaded"


def test_bad_day_does_not_touch_a_good_day(env):
    incoming, con, q = env
    generate_day(DAY, incoming)
    run_day(DAY, incoming, con, q)
    before = con.execute("SELECT count(*) FROM orders WHERE load_date = ?", [DAY]).fetchone()[0]
    d2 = DAY + timedelta(days=1)
    generate_day(d2, incoming)
    inject("null_key", incoming, d2)
    run_day(d2, incoming, con, q)
    assert con.execute("SELECT count(*) FROM orders WHERE load_date = ?", [DAY]).fetchone()[0] == before
