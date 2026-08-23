import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ai_client import AIClient, AIResponse, extract_json
from src.case_loader import get_case
from src.engine import diagnose

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cases.csv"


class _FakeUnavailableClient(AIClient):
    def is_available(self) -> bool:
        return False


class _FakeGoodClient(AIClient):
    def is_available(self) -> bool:
        return True

    def generate_json(self, instructions, case_input):
        return AIResponse(
            ok=True,
            raw_text=(
                '{"root_cause": "Sub-interface is administratively down.", '
                '"osi_layer": "Layer 1/2", "confidence": 0.9, '
                '"evidence": ["GigabitEthernet0/0.10 is administratively down"], '
                '"next_command": "show interfaces GigabitEthernet0/0.10", '
                '"fix_steps": ["no shutdown"], "concept": "Inter-VLAN Routing", '
                '"severity": "High", "explanation": "Matches deterministic finding.", '
                '"caveats": ""}'
            ),
            provider="fake",
            model="fake-model",
        )


class _FakeMalformedClient(AIClient):
    def is_available(self) -> bool:
        return True

    def generate_json(self, instructions, case_input):
        return AIResponse(ok=True, raw_text="not valid json at all {{{", provider="fake", model="fake-model")


class _FakeFailingClient(AIClient):
    def is_available(self) -> bool:
        return True

    def generate_json(self, instructions, case_input):
        return AIResponse(ok=False, error="simulated network timeout", provider="fake")


def _net001():
    return get_case("NET-001", csv_path=DATA_PATH)


def test_extract_json_direct():
    data = extract_json('{"a": 1, "b": 2}')
    assert data == {"a": 1, "b": 2}


def test_extract_json_with_markdown_fences():
    data = extract_json('```json\n{"a": 1}\n```')
    assert data == {"a": 1}


def test_extract_json_recovers_embedded_object():
    data = extract_json('Sure, here you go:\n{"a": 1, "b": "two"}\nHope that helps!')
    assert data == {"a": 1, "b": "two"}


def test_extract_json_returns_none_for_garbage():
    assert extract_json("not json at all") is None


def test_diagnose_no_ai_provider_falls_back_to_deterministic():
    case = _net001()
    findings, diag, status = diagnose(
        case.case_id, case.symptom, case.topology_note, case.show_outputs,
        ai_client=_FakeUnavailableClient(),
    )
    assert findings  # deterministic checker still finds something
    assert diag.source == "deterministic"
    assert diag.root_cause


def test_diagnose_with_good_ai_response():
    case = _net001()
    findings, diag, status = diagnose(
        case.case_id, case.symptom, case.topology_note, case.show_outputs,
        ai_client=_FakeGoodClient(),
    )
    assert diag.source.startswith("ai")
    assert diag.confidence == 0.9
    assert "administratively down" in diag.root_cause.lower()


def test_diagnose_with_malformed_ai_response_falls_back():
    case = _net001()
    findings, diag, status = diagnose(
        case.case_id, case.symptom, case.topology_note, case.show_outputs,
        ai_client=_FakeMalformedClient(),
    )
    # Must not crash; must fall back to deterministic-only diagnosis.
    assert diag.source == "deterministic"
    assert "malformed" in status.lower() or "deterministic" in status.lower()


def test_diagnose_with_failing_ai_call_falls_back():
    case = _net001()
    findings, diag, status = diagnose(
        case.case_id, case.symptom, case.topology_note, case.show_outputs,
        ai_client=_FakeFailingClient(),
    )
    assert diag.source == "deterministic"
    assert "simulated network timeout" in status or "deterministic" in status.lower()
