"""
src/engine.py

Orchestrates the full pipeline:

    evidence -> deterministic checker -> structured findings
             -> prompt construction -> AI call -> validated Diagnosis

The AI is never the sole source of truth: deterministic findings are
always computed first and are always shown to the user (and to the AI,
as authoritative signal). If the AI is unavailable, misconfigured, or
returns malformed output, the engine falls back to a deterministic-only
Diagnosis built directly from the rule-checker findings, and the UI is
told clearly that this happened.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.ai_client import AIClient, AIResponse, extract_json
from src.checker import run_checker
from src.models import Diagnosis, RuleResult

REQUIRED_DIAGNOSIS_FIELDS = [
    "root_cause",
    "osi_layer",
    "confidence",
    "evidence",
    "next_command",
    "fix_steps",
]

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "diagnose_prompt.md"


def _load_system_prompt() -> str:
    """Load the diagnosis instructions from the project prompt file."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Could not load diagnosis prompt: {exc}") from exc



def _format_findings(findings: List[RuleResult]) -> str:
    if not findings:
        return "(No deterministic rules matched this evidence.)"
    lines = []
    for f in findings:
        lines.append(
            f"- [{f.rule_id}] {f.title}\n"
            f"  root_cause: {f.root_cause}\n"
            f"  osi_layer: {f.osi_layer}\n"
            f"  severity: {f.severity}\n"
            f"  evidence: {'; '.join(f.evidence) if f.evidence else '(none)'}\n"
            f"  suggested_command: {f.suggested_command}\n"
            f"  suggested_fix: {f.suggested_fix}"
        )
    return "\n".join(lines)


def build_case_input(
    case_id: str,
    symptom: str,
    topology_note: str,
    show_outputs: str,
    findings: List[RuleResult],
) -> str:
    return f"""CASE: {case_id or '(custom / ad-hoc evidence)'}
SYMPTOM: {symptom}
TOPOLOGY: {topology_note}
CISCO EVIDENCE:
{show_outputs}

DETERMINISTIC FINDINGS:
{_format_findings(findings)}

Return ONLY the JSON diagnosis object described in your system instructions.
"""


def _deterministic_only_diagnosis(findings: List[RuleResult], note: str = "") -> Diagnosis:
    """Build a Diagnosis purely from deterministic findings, used when no
    AI provider is configured or the AI call/parse fails."""
    if findings:
        primary = findings[0]
        evidence = []
        for f in findings:
            evidence.extend(f.evidence)
        fix_steps = [f.suggested_fix for f in findings if f.suggested_fix]
        return Diagnosis(
            root_cause=primary.root_cause or primary.title,
            osi_layer=primary.osi_layer or "Unknown",
            confidence=0.6 if len(findings) == 1 else 0.5,
            evidence=evidence or ["No specific evidence snippet captured."],
            next_command=primary.suggested_command or "show running-config",
            fix_steps=fix_steps or ["Review the flagged configuration manually."],
            concept=primary.title,
            severity=primary.severity or "Medium",
            explanation=(
                "Deterministic-only diagnosis (no AI provider configured or AI call failed). "
                f"Based directly on rule-checker output.{(' ' + note) if note else ''}"
            ),
            deterministic_findings=[f.title for f in findings],
            caveats="This diagnosis was produced without AI assistance; treat it as a first pass and verify manually.",
            source="deterministic",
        )

    return Diagnosis(
        root_cause="No deterministic rule matched, and no AI diagnosis is available.",
        osi_layer="Unknown",
        confidence=0.1,
        evidence=[],
        next_command="show running-config",
        fix_steps=["Manually review the provided evidence; no automated match was found."],
        concept="Unclassified",
        severity="Unknown",
        explanation=(
            "Neither the deterministic checker nor the AI provider could produce a diagnosis. "
            f"{note}"
        ),
        deterministic_findings=[],
        caveats="No automated signal was available for this evidence.",
        source="deterministic",
    )


def _validate_and_build(data: dict, findings: List[RuleResult], provider: str) -> Optional[Diagnosis]:
    if not isinstance(data, dict):
        return None
    missing = [f for f in REQUIRED_DIAGNOSIS_FIELDS if f not in data]
    if missing:
        return None

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    evidence = data.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    fix_steps = data.get("fix_steps") or []
    if isinstance(fix_steps, str):
        fix_steps = [fix_steps]

    return Diagnosis(
        root_cause=str(data.get("root_cause", "")).strip(),
        osi_layer=str(data.get("osi_layer", "")).strip(),
        confidence=confidence,
        evidence=[str(e) for e in evidence],
        next_command=str(data.get("next_command", "")).strip(),
        fix_steps=[str(s) for s in fix_steps],
        concept=str(data.get("concept", "")).strip(),
        severity=str(data.get("severity", "")).strip(),
        explanation=str(data.get("explanation", "")).strip(),
        deterministic_findings=[f.title for f in findings],
        caveats=str(data.get("caveats", "")).strip(),
        source=f"ai:{provider}" if provider else "ai",
    )


def diagnose(
    case_id: str,
    symptom: str,
    topology_note: str,
    show_outputs: str,
    ai_client: Optional[AIClient] = None,
) -> tuple[List[RuleResult], Diagnosis, str]:
    """Run the full pipeline and return (findings, diagnosis, status_message).

    status_message explains, in plain language, whether AI was used and
    why (or why not), for display in the UI.
    """
    findings = run_checker(symptom, topology_note, show_outputs)

    client = ai_client or AIClient()

    if not client.is_available():
        diag = _deterministic_only_diagnosis(findings)
        return findings, diag, client.status_message()

    case_input = build_case_input(case_id, symptom, topology_note, show_outputs, findings)
    response: AIResponse = client.generate_json(_load_system_prompt(), case_input)

    if not response.ok:
        diag = _deterministic_only_diagnosis(findings, note=f"AI error: {response.error}")
        return findings, diag, f"AI call failed ({response.error}); showing deterministic-only result."

    parsed = extract_json(response.raw_text)
    diag = _validate_and_build(parsed, findings, response.provider) if parsed else None

    if diag is None:
        diag = _deterministic_only_diagnosis(
            findings,
            note="The AI response could not be parsed as valid JSON matching the schema.",
        )
        return findings, diag, "AI response was malformed; showing deterministic-only result."

    return findings, diag, f"AI diagnosis generated via {response.provider} ({response.model})."
