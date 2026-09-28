"""
Day 2 - Run the data-quality suite against orders.csv.

Run:  python run.py      (after: python generate_data.py)

What happens:
  1. Load orders.csv
  2. Declare the rules (the "contract" the data must satisfy)
  3. Execute all rules -> QualityReport (console table + score)
  4. Write output/quality_report.json (machine-readable, for CI / dashboards)
  5. Write output/quarantined_rows.csv (union of every failing row)
"""

import json
import os

import pandas as pd

from checks import (
    check_custom,
    check_in_range,
    check_is_in,
    check_matches_regex,
    check_not_future_date,
    check_not_null,
    check_unique,
    quarantine_index,
    run_checks,
)

# ---------------- 1. LOAD ----------------
df = pd.read_csv("orders.csv")
print(f"Loaded {len(df)} rows from orders.csv\n")

# ---------------- 2. DECLARE THE RULES ----------------
# This list IS the data contract. Add a rule here and it runs everywhere
# this suite runs -- locally, on Replit, or in CI.
rules = [
    check_not_null("order_id"),                       # every row needs an id
    check_unique("order_id"),                         # ...and it must be unique
    check_not_null("customer_email"),
    check_matches_regex(
        "customer_email",
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",                # local@domain.tld, no spaces
        label="valid email",
    ),
    check_is_in("product_category",
                ["electronics", "clothing", "books", "home", "sports"]),
    check_in_range("price", 0.01, 100_000),           # positive, sane upper bound
    check_in_range("quantity", 1, 1000),
    check_not_future_date("order_date"),
    check_is_in("country", ["US", "CA", "UK", "IN", "AU", "DE"]),
    # Custom rule example: flag suspicious bulk buys (non-critical: reports only).
    # Threshold 50 sits above all seeded data, so this rule PASSES today --
    # try lowering it to 15 and re-running to watch it fire.
    check_custom(
        "quantity", "bulk_buy_review",
        lambda df, c: pd.to_numeric(df[c], errors="coerce") > 50,
        critical=False,
    ),
]

# ---------------- 3. RUN + REPORT ----------------
report = run_checks(df, rules)
print(report.pretty())

print("\nSample failing rows:")
for r in report.failed:
    print(f"\n  [{r.name} on '{r.column}'] {r.fail_count} failing row(s), e.g.:")
    for ex in r.failing_examples[:2]:
        print(f"    {ex}")

# ---------------- 4. WRITE ARTIFACTS ----------------
os.makedirs("output", exist_ok=True)

with open("output/quality_report.json", "w") as f:
    json.dump(report.to_dict(), f, indent=2)
print("\nWrote output/quality_report.json")

# Quarantine: every row that failed ANY rule, annotated with which rules failed.
q_idx = quarantine_index(df, rules)
quarantined = df.loc[q_idx].copy()

# For each quarantined row, list the names of the rules it failed.
failed_sets = {i: [] for i in q_idx}
for rule in rules:
    mask = rule.test(df, rule.column).fillna(False).astype(bool)
    for i in df.index[mask]:
        failed_sets[i].append(rule.name)
quarantined["failed_rules"] = [", ".join(sorted(failed_sets[i])) for i in q_idx]
quarantined.to_csv("output/quarantined_rows.csv", index=False)
print(f"Wrote output/quarantined_rows.csv ({len(quarantined)} quarantined rows)")

print(f"\nOverall: {report.overall}  |  Quality score: {report.quality_score}/100")
