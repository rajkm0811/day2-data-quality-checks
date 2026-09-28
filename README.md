# Day 2 — Data Quality Checks: a tiny DQ framework from scratch

A mini data-quality framework in pure Python + pandas — the same core idea
as Great Expectations / Soda, without the dependency: declare rules as data,
run them all, get a quality score, a machine-readable report, and a
quarantined set of bad rows.

## What it demonstrates

- **Data contracts**: the `rules` list in `run.py` is the contract the data
  must satisfy — the same pattern production pipelines use before a load.
- **Rule engine**: each `Rule` is a named test bound to a column that returns
  a boolean mask of *failing* rows. Adding a new check = one line.
- **Quality score**: mean per-rule pass rate (0–100), so one bad column can't
  hide behind many passing ones.
- **Critical vs. non-critical**: critical failures flip the overall verdict to
  FAIL — this is what a CI gate reads to block a bad load.
- **Quarantine pattern** (from Day 1, leveled up): failing rows are written
  aside with a `failed_rules` column naming exactly which rules each row
  failed — bad data is counted *and* explainable.

## Files

| File | Purpose |
|---|---|
| `generate_data.py` | Creates `orders.csv`: 112 clean + 15 dirty rows (seeded) |
| `checks.py` | The framework: `Rule`, check factories, `QualityReport`, `run_checks` |
| `run.py` | Declares the rules, runs the suite, writes the artifacts |

## Run it

```bash
pip install pandas
python generate_data.py
python run.py
```

On Replit: New Repl → Python → upload the three `.py` files → in the Shell
tab run `pip install pandas`, then `python generate_data.py` and
`python run.py` (or press Run after setting the run command).

## Expected output

- Console: a PASS/FAIL table per rule, sample failing rows, overall verdict
- `output/quality_report.json`: full machine-readable report (score, per-rule
  pass rates, failing-row samples, timestamp)
- `output/quarantined_rows.csv`: every row that failed any rule, annotated
  with which rules it failed

With the seeded data: 126 rows in, 10 rules run, 9 fail (1 passes),
14 rows quarantined, quality score 98.81/100, overall verdict FAIL
(critical rules failed — exactly what a CI gate should block on).

## Try it yourself

- Add a rule to the `rules` list in `run.py` (e.g. `check_in_range("price", 0.01, 500)`)
- Flip a rule to `critical=False` and watch the overall verdict change
- Write a `check_custom` rule for your own business logic

Part of a daily data-engineering build series. Day 1: mini ETL pipeline
(CSV → clean → validate → partitioned Parquet).
