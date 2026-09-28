"""
Day 2 - A tiny data-quality framework you can reuse in any pipeline.

Design (deliberately minimal, like the core of Great Expectations / Soda):
  * A Rule is a named test bound to one column. Its job is to return a
    boolean mask of the FAILING rows (True = this row failed).
  * A check factory (check_not_null, check_in_range, ...) builds Rules.
  * run_checks() executes every rule against a DataFrame and returns a
    QualityReport with a 0-100 quality score, failing-row samples and a
    PASS/FAIL verdict driven by critical rules.

Stdlib + pandas only. No external DQ library needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd


# ---------------------------------------------------------------- Rule ----
class Rule:
    """One named data-quality test bound to a column.

    `test(df, column)` must return a boolean pandas Series where True marks
    a FAILING row. `critical=True` means a failure flips the whole report
    to FAIL (the pattern CI gates use to block a bad load).
    """

    def __init__(self, name, column, test, critical=True):
        self.name = name
        self.column = column
        self.test = test
        self.critical = critical

    def run(self, df):
        mask = self.test(df, self.column).fillna(False).astype(bool)
        failed = df.index[mask]
        return CheckResult(
            name=self.name,
            column=self.column,
            critical=self.critical,
            passed=len(failed) == 0,
            fail_count=len(failed),
            total=len(df),
            failing_examples=df.loc[failed].head(5).to_dict("records"),
        )


# ------------------------------------------------------- Check result ----
def _json_safe(value):
    """Recursively convert NaN/NaT/pd.NA to None so json.dump() emits
    valid JSON (the default would write a bare NaN literal, which strict
    JSON parsers reject -- bad for a CI-consumed report)."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


@dataclass
class CheckResult:
    name: str
    column: str
    passed: bool
    fail_count: int
    total: int
    critical: bool = True
    failing_examples: list = field(default_factory=list)

    @property
    def pass_rate(self):
        return (self.total - self.fail_count) / self.total if self.total else 1.0

    def to_dict(self):
        return {
            "name": self.name,
            "column": self.column,
            "critical": self.critical,
            "passed": self.passed,
            "fail_count": self.fail_count,
            "total": self.total,
            "pass_rate": round(self.pass_rate, 4),
            "failing_examples": _json_safe(self.failing_examples),
        }


# ---------------------------------------------------------- Check makers ----
def check_not_null(column, critical=True):
    """Fail rows where the value is missing: NaN, None, or blank string.

    astype(str) on NaN gives "nan", so we OR the isna() check with a
    stripped-empty-string check to catch "" and "   " too.
    """
    def _test(df, c):
        s = df[c]
        return s.isna() | (s.astype(str).str.strip() == "")

    return Rule("not_null", column, _test, critical)


def check_unique(column, critical=True):
    """Fail duplicate values (first occurrence is kept, later ones fail)."""
    return Rule(
        "unique",
        column,
        lambda df, c: df.duplicated(subset=[c], keep="first"),
        critical,
    )


def check_in_range(column, low, high, critical=True):
    """Fail values outside [low, high]. Non-numeric values also fail
    (to_numeric(errors='coerce') turns garbage into NaN, and NaN fails)."""
    def _test(df, c):
        vals = pd.to_numeric(df[c], errors="coerce")
        return vals.isna() | (vals < low) | (vals > high)

    return Rule(f"in_range[{low},{high}]", column, _test, critical)


def check_matches_regex(column, pattern, label=None, critical=True):
    """Fail values that don't match the regex. `na=False` makes missing
    values count as failures (a null email is not a valid email)."""
    rx = re.compile(pattern)

    def _test(df, c):
        return ~df[c].astype(str).str.match(rx, na=False)

    return Rule(f"regex[{label or pattern}]", column, _test, critical)


def check_is_in(column, allowed, critical=True):
    """Fail values outside an allowed set (categorical/domain check)."""
    allowed_set = set(allowed)
    return Rule(
        f"is_in[{len(allowed_set)} values]",
        column,
        lambda df, c: ~df[c].isin(allowed_set),
        critical,
    )


def check_not_future_date(column, critical=True):
    """Fail dates after 'now' (source-system clock skew / bad ETL)."""

    def _test(df, c):
        dates = pd.to_datetime(df[c], errors="coerce")
        return dates.isna() | (dates > pd.Timestamp.now())

    return Rule("not_future_date", column, _test, critical)


def check_custom(column, name, predicate, critical=False):
    """Escape hatch: `predicate(df, column)` returns the failing-row mask.
    Non-critical by default -- custom rules report without blocking."""
    return Rule(name, column, predicate, critical)


# ------------------------------------------------------------- Report ----
@dataclass
class QualityReport:
    results: list
    total_rows: int
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def failed(self):
        return [r for r in self.results if not r.passed]

    @property
    def overall(self):
        """FAIL if any critical rule failed -- this is what a CI gate reads."""
        return "PASS" if not any(r.critical and not r.passed for r in self.results) else "FAIL"

    @property
    def quality_score(self):
        """Mean per-rule pass rate, 0-100. One bad column can't be hidden
        behind many passing ones the way a flat row-count ratio could."""
        if not self.results:
            return 100.0
        return round(sum(r.pass_rate for r in self.results) / len(self.results) * 100, 2)

    def to_dict(self):
        return {
            "ran_at": self.ran_at,
            "total_rows": self.total_rows,
            "overall": self.overall,
            "quality_score": self.quality_score,
            "rules_run": len(self.results),
            "rules_failed": len(self.failed),
            "results": [r.to_dict() for r in self.results],
        }

    def pretty(self):
        lines = []
        lines.append(f"{'STATUS':<6} {'RULE':<28} {'COLUMN':<18} {'FAILED':>7} {'PASS%':>7}")
        lines.append("-" * 72)
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"{status:<6} {r.name:<28} {r.column:<18} "
                f"{r.fail_count:>7} {r.pass_rate * 100:>6.1f}%"
            )
        lines.append("-" * 72)
        lines.append(f"Quality score: {self.quality_score}/100   Overall: {self.overall}")
        return "\n".join(lines)


def run_checks(df, rules):
    """Execute every rule, return a QualityReport."""
    return QualityReport(results=[rule.run(df) for rule in rules], total_rows=len(df))


def quarantine_index(df, rules):
    """Union of failing-row indexes across all rules (the quarantine set)."""
    idx = set()
    for rule in rules:
        mask = rule.test(df, rule.column).fillna(False).astype(bool)
        idx.update(df.index[mask].tolist())
    return sorted(idx)
