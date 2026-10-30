"""Run the full analytics pipeline end to end: python run_pipeline.py"""
import os
import subprocess
import sys

STEPS = [
    "load_data.py",                 # 1. CSVs -> SQLite (data/processed/olist.db)
    "build_and_validate_abt.py",    # 2. Build order-grain mart + integrity checks
    "run_business_analytics.py",    # 3. GMV, AOV, MoM growth, top categories
    "run_operations_analytics.py",  # 4. Delivery SLA vs. reviews, late states
    "run_customer_analytics.py",    # 5. Repeat rate, RFM, cohort retention
    "run_statistical_tests.py",     # 6. Hypothesis tests
]

root = os.path.dirname(os.path.abspath(__file__))
for step in STEPS:
    print(f"\n{'#' * 70}\n# Running {step}\n{'#' * 70}")
    if subprocess.run([sys.executable, os.path.join(root, step)], cwd=root).returncode != 0:
        sys.exit(f"[FAIL] {step} failed - stopping pipeline.")
print("\n[DONE] Pipeline complete. Charts: reports/figures/  Tables: reports/tables/")
