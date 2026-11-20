#!/usr/bin/env python3
"""Inject every fault, check each is caught, and write results to app_data/ for the Streamlit monitor.

Usage:  python scripts/run_chaos_suite.py
Exit code 1 if any fault slips through, so CI can fail on it.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from chaos.suite import run_suite  # noqa: E402

if __name__ == "__main__":
    s = run_suite(ROOT / "app_data")
    print(s)
    ok = s["faults_caught"] == s["faults_injected"] == s["caught_by_expected_rule"] and s["duplicate_order_ids_after_reruns"] == 0
    print("PASS: every fault caught by the expected rule, reruns left no duplicates" if ok else "FAIL")
    sys.exit(0 if ok else 1)
