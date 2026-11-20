"""Fault injection: break a day's source file on purpose. Each fault edits the CSV (and sometimes removes it)."""
import random
from datetime import date
from pathlib import Path

import pandas as pd

# fault name -> the contract or reconciliation rule that should catch it
EXPECTED_CATCH = {
    "duplicate_rows": "unique",
    "null_key": "nullable",
    "schema_rename": "schema",
    "type_change": "type",
    "out_of_range": "range",
    "bad_category": "allowed",
    "volume_drop": "volume",
    "silent_truncate": "reconciliation",
    "missing_file": "freshness",
}


def _path(incoming: Path, day: date) -> Path:
    return incoming / f"orders_{day:%Y-%m-%d}.csv"


def inject(fault: str, incoming: Path, day: date, seed: int = 1) -> None:
    """Apply one fault to the day's file. The manifest is left untouched, like a real source that reports its own totals."""
    rng = random.Random(f"{fault}-{day}-{seed}")
    p = _path(incoming, day)
    if fault == "missing_file":
        p.unlink()
        return
    df = pd.read_csv(p, dtype=str)
    if fault == "duplicate_rows":
        df = pd.concat([df, df.sample(5, random_state=seed)], ignore_index=True)
    elif fault == "null_key":
        df.loc[df.sample(4, random_state=seed).index, "order_id"] = ""
    elif fault == "schema_rename":
        df = df.rename(columns={"amount": "amt"})
    elif fault == "type_change":
        df.loc[df.sample(6, random_state=seed).index, "amount"] = "N/A"
    elif fault == "out_of_range":
        df.loc[df.sample(3, random_state=seed).index, "amount"] = "-50.00"
    elif fault == "bad_category":
        df.loc[df.sample(7, random_state=seed).index, "currency"] = "XXX"
    elif fault == "volume_drop":
        df = df.sample(frac=0.1, random_state=seed)
    elif fault == "silent_truncate":
        df = df.iloc[: len(df) - rng.randint(3, 6)]  # a few rows lost: still a normal-looking file
    else:
        raise ValueError(f"unknown fault: {fault}")
    df.to_csv(p, index=False)
