# Chaos-proof pipelines

Pipelines that survive bad data, late data and reruns: data contracts, reconciliation, idempotent backfills and alerts.

**Status:** planned, build starts in week 4. All data is public or synthetic. No employer data is used.

## Plan

1. Write data contracts for each source.
2. Build Dagster assets with reconciliation checks and a run log.
3. Add a failure injector and prove every fault is caught.
4. Make backfills safe to rerun, add alerts and a Streamlit chaos monitor.

## Part of a series

This is one of six portfolio projects. The first one, [patient-360](https://github.com/agshivam/patient-360), is already live with a [running report](https://patient-360.streamlit.app/). Portfolio: https://agshivam.github.io
