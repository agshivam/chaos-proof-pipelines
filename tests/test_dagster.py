import sys
from pathlib import Path

import pytest

dg = pytest.importorskip("dagster")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "orchestration"))


def test_two_partitions_materialize(tmp_path, monkeypatch):
    import definitions as d
    monkeypatch.setattr(d, "DATA", tmp_path)
    for key in ("2026-11-01", "2026-11-02"):
        result = dg.materialize([d.source_orders_file, d.orders], partition_key=key)
        assert result.success
