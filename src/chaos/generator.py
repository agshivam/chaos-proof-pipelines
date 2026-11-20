"""Generate a clean synthetic daily orders file plus a control-total manifest, the same way a source system would."""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

CURRENCIES = ["USD", "EUR", "GBP", "INR"]
STATUSES = ["placed", "shipped", "delivered", "cancelled"]


def generate_day(day: date, incoming: Path, seed: int = 7, rows: int | None = None) -> pd.DataFrame:
    """Write orders_<date>.csv and manifest_<date>.json into `incoming`. Deterministic for a given day and seed."""
    rng = random.Random(f"{seed}-{day.isoformat()}")
    n = rows or rng.randint(180, 220)
    base = datetime(day.year, day.month, day.day)
    data = {
        "order_id": [f"O{day:%Y%m%d}{i:05d}" for i in range(n)],
        "customer_id": [f"C{rng.randint(1, 800):04d}" for _ in range(n)],
        "order_ts": [(base + timedelta(seconds=rng.randint(0, 86399))).strftime("%Y-%m-%d %H:%M:%S") for _ in range(n)],
        "amount": [round(rng.uniform(5, 900), 2) for _ in range(n)],
        "currency": [rng.choice(CURRENCIES) for _ in range(n)],
        "status": [rng.choice(STATUSES) for _ in range(n)],
    }
    df = pd.DataFrame(data)
    incoming.mkdir(parents=True, exist_ok=True)
    df.to_csv(incoming / f"orders_{day:%Y-%m-%d}.csv", index=False)
    manifest = {"date": day.isoformat(), "row_count": n, "amount_sum": round(float(df["amount"].sum()), 2)}
    (incoming / f"manifest_{day:%Y-%m-%d}.json").write_text(json.dumps(manifest))
    return df
