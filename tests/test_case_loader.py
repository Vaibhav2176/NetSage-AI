import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.case_loader import (
    CaseLoadError,
    get_case,
    load_cases,
    search_cases,
)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cases.csv"


def test_load_cases_returns_30():
    cases = load_cases(csv_path=DATA_PATH, strict_count=True)
    assert len(cases) == 30


def test_all_case_ids_present_and_unique():
    cases = load_cases(csv_path=DATA_PATH)
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))
    expected_ids = {f"NET-{i:03d}" for i in range(1, 31)}
    assert set(ids) == expected_ids


def test_get_case_found():
    case = get_case("NET-001", csv_path=DATA_PATH)
    assert case is not None
    assert case.case_id == "NET-001"
    assert "administratively down" in case.show_outputs.lower()


def test_get_case_case_insensitive():
    case = get_case("net-002", csv_path=DATA_PATH)
    assert case is not None
    assert case.case_id == "NET-002"


def test_get_case_not_found():
    case = get_case("NET-999", csv_path=DATA_PATH)
    assert case is None


def test_search_cases_by_concept_tag():
    results = search_cases(concept_tag="DHCP", csv_path=DATA_PATH)
    assert len(results) >= 1
    for r in results:
        assert r.concept_tag.lower() == "dhcp"


def test_search_cases_free_text():
    results = search_cases(query="ospf", csv_path=DATA_PATH)
    assert any(r.case_id == "NET-004" for r in results)


def test_missing_csv_raises(tmp_path):
    missing = tmp_path / "does_not_exist.csv"
    with pytest.raises(CaseLoadError):
        load_cases(csv_path=missing)


def test_malformed_csv_missing_columns(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("case_id,symptom\nNET-001,test\n", encoding="utf-8")
    with pytest.raises(CaseLoadError):
        load_cases(csv_path=bad_csv)


def test_duplicate_case_id_raises(tmp_path):
    header = "case_id,symptom,topology_note,show_outputs,expected_fault,osi_layer,concept_tag,severity\n"
    row = "NET-001,a,b,c,d,Layer 3,Test,High\n"
    dup_csv = tmp_path / "dup.csv"
    dup_csv.write_text(header + row + row, encoding="utf-8")
    with pytest.raises(CaseLoadError):
        load_cases(csv_path=dup_csv)
