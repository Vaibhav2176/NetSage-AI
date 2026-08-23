"""
src/case_loader.py

Loads and validates the authoritative case dataset from data/cases.csv.

The dataset is never duplicated inside Python source. Everything in this
module reads the CSV dynamically.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from src.models import Case

REQUIRED_COLUMNS = [
    "case_id",
    "symptom",
    "topology_note",
    "show_outputs",
    "expected_fault",
    "osi_layer",
    "concept_tag",
    "severity",
]

EXPECTED_CASE_COUNT = 30

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "cases.csv"


class CaseLoadError(Exception):
    """Raised when the case CSV is missing, malformed, or fails validation."""


def load_cases(csv_path: Optional[Path] = None, strict_count: bool = False) -> List[Case]:
    """Load all cases from the CSV file.

    Args:
        csv_path: Optional override path. Defaults to data/cases.csv.
        strict_count: If True, raise if the file does not contain exactly
            EXPECTED_CASE_COUNT rows. The Streamlit app uses strict_count=False
            so that a trimmed demo CSV still loads (with a warning), while the
            evaluator / tests can request strict_count=True.

    Returns:
        List of Case objects, in file order.

    Raises:
        CaseLoadError: on missing file, missing columns, or duplicate IDs.
    """
    path = csv_path or DEFAULT_CSV_PATH

    if not path.exists():
        raise CaseLoadError(f"Case dataset not found at: {path}")

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = [c.strip() for c in (reader.fieldnames or [])]
            missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
            if missing:
                raise CaseLoadError(
                    f"cases.csv is missing required column(s): {missing}. "
                    f"Found columns: {fieldnames}"
                )

            cases: List[Case] = []
            seen_ids = set()
            for row_num, row in enumerate(reader, start=2):  # header is line 1
                case_id = (row.get("case_id") or "").strip()
                if not case_id:
                    # Skip fully blank trailing rows gracefully.
                    if not any((v or "").strip() for v in row.values()):
                        continue
                    raise CaseLoadError(f"Row {row_num} is missing a case_id.")

                if case_id in seen_ids:
                    raise CaseLoadError(f"Duplicate case_id found: {case_id}")
                seen_ids.add(case_id)

                try:
                    case = Case(
                        case_id=case_id,
                        symptom=(row.get("symptom") or "").strip(),
                        topology_note=(row.get("topology_note") or "").strip(),
                        show_outputs=(row.get("show_outputs") or "").strip(),
                        expected_fault=(row.get("expected_fault") or "").strip(),
                        osi_layer=(row.get("osi_layer") or "").strip(),
                        concept_tag=(row.get("concept_tag") or "").strip(),
                        severity=(row.get("severity") or "").strip(),
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    raise CaseLoadError(f"Row {row_num} ({case_id}) is malformed: {exc}") from exc

                cases.append(case)

    except CaseLoadError:
        raise
    except Exception as exc:
        raise CaseLoadError(f"Failed to read cases.csv: {exc}") from exc

    if not cases:
        raise CaseLoadError("cases.csv contains no usable rows.")

    if strict_count and len(cases) != EXPECTED_CASE_COUNT:
        raise CaseLoadError(
            f"Expected exactly {EXPECTED_CASE_COUNT} cases, found {len(cases)}."
        )

    return cases


def get_all_cases(csv_path: Optional[Path] = None) -> List[Case]:
    """Convenience alias for load_cases()."""
    return load_cases(csv_path=csv_path)


def get_case(case_id: str, csv_path: Optional[Path] = None) -> Optional[Case]:
    """Look up a single case by its case_id (case-insensitive)."""
    if not case_id:
        return None
    normalized = case_id.strip().upper()
    for case in load_cases(csv_path=csv_path):
        if case.case_id.strip().upper() == normalized:
            return case
    return None


def search_cases(
    query: str = "",
    concept_tag: Optional[str] = None,
    severity: Optional[str] = None,
    osi_layer: Optional[str] = None,
    csv_path: Optional[Path] = None,
) -> List[Case]:
    """Search/filter cases by free-text query and/or exact-match filters.

    The free-text query matches (case-insensitively) against symptom,
    topology_note, show_outputs, and expected_fault.
    """
    cases = load_cases(csv_path=csv_path)
    q = (query or "").strip().lower()

    def matches(case: Case) -> bool:
        if q:
            haystack = " ".join(
                [
                    case.symptom,
                    case.topology_note,
                    case.show_outputs,
                    case.expected_fault,
                    case.case_id,
                ]
            ).lower()
            if q not in haystack:
                return False
        if concept_tag and case.concept_tag.strip().lower() != concept_tag.strip().lower():
            return False
        if severity and case.severity.strip().lower() != severity.strip().lower():
            return False
        if osi_layer and case.osi_layer.strip().lower() != osi_layer.strip().lower():
            return False
        return True

    return [c for c in cases if matches(c)]


def cases_index(csv_path: Optional[Path] = None) -> Dict[str, Case]:
    """Return a dict of case_id -> Case for quick lookups."""
    return {c.case_id: c for c in load_cases(csv_path=csv_path)}
