"""Load a data contract and check a day's data against it. Returns a list of violations, never raises on bad data."""
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd
import yaml


@dataclass
class Violation:
    rule: str          # schema, nullable, type, unique, range, allowed, volume
    column: str
    count: int
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def load_contract(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def _is_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").notna()


def _is_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).notna()


def validate(df: pd.DataFrame, contract: dict) -> list[Violation]:
    """Check a DataFrame read with every column as text. Checks run in a fixed order, so results are stable."""
    out: list[Violation] = []
    cols = contract["columns"]

    missing = [c for c in cols if c not in df.columns]
    extra = [c for c in df.columns if c not in cols]
    if missing or extra:
        out.append(Violation("schema", ",".join(missing + extra), len(missing) + len(extra),
                             f"missing columns {missing}, unexpected columns {extra}"))
        return out  # nothing else can be trusted without the right columns

    for name, rule in cols.items():
        s = df[name]
        blank = s.isna() | (s.astype(str).str.strip() == "")
        if not rule.get("nullable", True) and blank.any():
            out.append(Violation("nullable", name, int(blank.sum()), "empty values in a required column"))
        present = s[~blank]
        typ = rule["type"]
        if typ == "double":
            bad = ~_is_number(present)
        elif typ == "timestamp":
            bad = ~_is_timestamp(present)
        else:
            bad = pd.Series(False, index=present.index)
        if bad.any():
            out.append(Violation("type", name, int(bad.sum()), f"values that are not {typ}"))
            continue  # range checks need numbers
        if typ == "double" and ("min" in rule or "max" in rule):
            nums = pd.to_numeric(present)
            low = nums < rule.get("min", float("-inf"))
            high = nums > rule.get("max", float("inf"))
            if (low | high).any():
                out.append(Violation("range", name, int((low | high).sum()),
                                     f"values outside {rule.get('min')} to {rule.get('max')}"))
        if "allowed" in rule:
            bad = ~present.isin(rule["allowed"])
            if bad.any():
                out.append(Violation("allowed", name, int(bad.sum()), f"values not in {rule['allowed']}"))
        if rule.get("unique"):
            dup = present.duplicated(keep=False)
            if dup.any():
                out.append(Violation("unique", name, int(present[dup].nunique()), "duplicate values in a unique column"))

    vol = contract.get("volume")
    if vol:
        low = vol["expected_rows"] * (1 - vol["tolerance_pct"] / 100)
        high = vol["expected_rows"] * (1 + vol["tolerance_pct"] / 100)
        if not (low <= len(df) <= high):
            out.append(Violation("volume", "*", len(df), f"{len(df)} rows, expected {low:.0f} to {high:.0f}"))
    return out
