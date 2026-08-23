#!/usr/bin/env python3
"""
evaluate.py

Runs the deterministic checker against all 30 cases in data/cases.csv
and compares the top matched rule's title against each case's
expected_fault column, using fuzzy text comparison (see src/utils.py)
so that wording/punctuation differences don't cause spurious mismatches.

Usage:
    python evaluate.py            # human-readable table + summary
    python evaluate.py --json     # machine-readable JSON report

This does not call any AI provider — it evaluates the deterministic
layer only, which is required to work even with zero API keys
configured.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.case_loader import load_cases
from src.checker import run_checker
from src.utils import fuzzy_match


def evaluate() -> dict:
    cases = load_cases(strict_count=False)
    rows = []
    correct = 0
    missed = 0

    for case in cases:
        findings = run_checker(case.symptom, case.topology_note, case.show_outputs)
        detected = findings[0].title if findings else ""
        match = bool(detected) and fuzzy_match(case.expected_fault, detected)
        if not findings:
            missed += 1
        elif match:
            correct += 1

        rows.append(
            {
                "case_id": case.case_id,
                "expected_fault": case.expected_fault,
                "detected_fault": detected or "(no match)",
                "match": match,
                "all_findings": [f.title for f in findings],
            }
        )

    total = len(cases)
    false_positive_like = total - correct - missed  # matched something, but not a fuzzy match
    summary = {
        "total_cases": total,
        "correct_deterministic_detections": correct,
        "missed": missed,
        "mismatched_detection": false_positive_like,
        "accuracy_pct": round((correct / total) * 100, 1) if total else 0.0,
    }
    return {"summary": summary, "rows": rows}


def print_report(report: dict) -> None:
    rows = report["rows"]
    summary = report["summary"]

    print(f"{'Case':<9} {'Match':<6} {'Expected':<45} {'Detected'}")
    print("-" * 110)
    for r in rows:
        mark = "YES" if r["match"] else "no"
        print(f"{r['case_id']:<9} {mark:<6} {r['expected_fault'][:43]:<45} {r['detected_fault']}")

    print("\nSummary")
    print("-------")
    print(f"Total cases: {summary['total_cases']}")
    print(f"Correct deterministic detections: {summary['correct_deterministic_detections']}")
    print(f"Missed (no rule matched): {summary['missed']}")
    print(f"Mismatched (a rule matched, but not the expected fault): {summary['mismatched_detection']}")
    print(f"Accuracy: {summary['accuracy_pct']}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate NetSage AI deterministic checker against cases.csv")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a table")
    args = parser.parse_args()

    report = evaluate()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
