import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.case_loader import get_case, load_cases
from src.checker import run_checker
from src.utils import fuzzy_match

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cases.csv"


def _findings_for(case_id: str):
    case = get_case(case_id, csv_path=DATA_PATH)
    assert case is not None, f"{case_id} not found in dataset"
    return case, run_checker(case.symptom, case.topology_note, case.show_outputs)


def test_interface_admin_down_detection():
    case, findings = _findings_for("NET-001")
    assert any("administratively down" in f.title.lower() for f in findings)


def test_dhcp_pool_exhaustion_detection():
    case, findings = _findings_for("NET-002")
    assert any("dhcp" in f.title.lower() and "pool" in f.title.lower() for f in findings)


def test_dns_disabled_detection():
    case, findings = _findings_for("NET-003")
    assert any("dns" in f.title.lower() for f in findings)


def test_ospf_hello_mismatch_detection():
    case, findings = _findings_for("NET-004")
    assert any("ospf" in f.title.lower() and "hello" in f.title.lower() for f in findings)


def test_acl_detection():
    case, findings = _findings_for("NET-005")
    assert any("acl" in f.title.lower() for f in findings)


def test_nat_pat_detection():
    case, findings = _findings_for("NET-006")
    assert any("nat" in f.title.lower() or "pat" in f.title.lower() or "overload" in f.title.lower() for f in findings)


def test_vlan_trunk_detection():
    case, findings = _findings_for("NET-008")
    assert any("trunk" in f.title.lower() for f in findings)


def test_wrong_gateway_detection():
    case, findings = _findings_for("NET-009")
    assert any("gateway" in f.title.lower() for f in findings)


def test_missing_route_related_detection():
    case, findings = _findings_for("NET-015")
    assert any("route" in f.title.lower() or "next hop" in f.title.lower() or "next-hop" in f.title.lower() for f in findings)


def test_duplicate_ip_detection():
    case, findings = _findings_for("NET-023")
    assert any("duplicate" in f.title.lower() for f in findings)


def test_malformed_evidence_does_not_crash():
    # Garbage / empty input should never raise, and should return an
    # empty (or harmless) findings list rather than crashing the app.
    findings = run_checker("", "", "")
    assert isinstance(findings, list)

    findings = run_checker(None, None, None)  # type: ignore[arg-type]
    assert isinstance(findings, list)

    findings = run_checker("normal text with no cisco content", "just words", "banana banana banana")
    assert isinstance(findings, list)


def test_all_30_cases_produce_at_least_one_finding():
    cases = load_cases(csv_path=DATA_PATH)
    misses = []
    for case in cases:
        findings = run_checker(case.symptom, case.topology_note, case.show_outputs)
        if not findings:
            misses.append(case.case_id)
    assert not misses, f"No deterministic finding for: {misses}"


def test_evaluator_accuracy_is_reasonable():
    """Sanity check: the deterministic checker's top finding should
    fuzzy-match the expected_fault for a strong majority of the 30
    cases. This does not assert 100% - see evaluate.py for the honest,
    exact figure."""
    cases = load_cases(csv_path=DATA_PATH)
    correct = 0
    for case in cases:
        findings = run_checker(case.symptom, case.topology_note, case.show_outputs)
        if findings and fuzzy_match(case.expected_fault, findings[0].title):
            correct += 1
    accuracy = correct / len(cases)
    assert accuracy >= 0.8, f"Deterministic accuracy too low: {accuracy:.2%}"
