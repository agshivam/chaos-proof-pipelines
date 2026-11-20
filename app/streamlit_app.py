"""Chaos monitor: every fault injected, whether it was caught, which rule caught it, and how fast."""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parent.parent / "app_data"
st.set_page_config(page_title="Chaos monitor", layout="wide")

if not (DATA / "summary.parquet").exists():
    st.error("No results yet. Run: python scripts/run_chaos_suite.py")
    st.stop()

summary = pd.read_parquet(DATA / "summary.parquet").iloc[0]
faults = pd.read_parquet(DATA / "faults.parquet")
runs = pd.read_parquet(DATA / "runs.parquet")
per_day = pd.read_parquet(DATA / "per_day.parquet")

st.title("Chaos monitor")
st.caption("Synthetic orders data. A generator breaks the source file on purpose; contracts and reconciliation must catch it.")

c = st.columns(4)
c[0].metric("Faults injected", int(summary.faults_injected))
c[1].metric("Faults caught", int(summary.faults_caught))
c[2].metric("Caught by the expected rule", int(summary.caught_by_expected_rule))
c[3].metric("Duplicate orders after reruns", int(summary.duplicate_order_ids_after_reruns))

t1, t2, t3 = st.tabs(["Faults", "Run history", "Loaded data"])
with t1:
    shown = faults.rename(columns={"fault": "Fault", "expected_rule": "Expected rule", "caught_by": "Caught by",
                                   "caught": "Caught", "correct_rule": "Right rule", "detect_ms": "Detected in (ms)"})
    st.dataframe(shown, width="stretch", hide_index=True)
    st.altair_chart(alt.Chart(faults).mark_bar(color="#1F6F8B").encode(
        x=alt.X("detect_ms:Q", title="Time to detect (ms)"), y=alt.Y("fault:N", sort="-x", title=None),
        tooltip=["fault", "caught_by", "detect_ms"]), width="stretch")
    st.caption("Most faults are caught by a contract rule. 'silent_truncate' loses a few rows but still looks like a normal file, "
               "so only reconciliation against the source's control totals catches it.")
with t2:
    counts = runs.groupby("status").size().reset_index(name="runs")
    st.altair_chart(alt.Chart(counts).mark_bar(color="#1F6F8B").encode(x="status:N", y="runs:Q", tooltip=["status", "runs"]), width="stretch")
    st.dataframe(runs, width="stretch", hide_index=True)
with t3:
    st.altair_chart(alt.Chart(per_day).mark_bar(color="#1F6F8B").encode(
        x=alt.X("load_date:T", title="Day"), y=alt.Y("rows:Q", title="Rows loaded"), tooltip=["load_date", "rows", "amount"]), width="stretch")
    st.caption("Each day appears once, even though bad files were rejected and later resent: reruns replace a day, never add to it.")
