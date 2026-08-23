"""
src/models.py

Plain dataclasses used across the NetSage AI project.

Keeping these in one place means every module (case_loader, checker,
engine, ai_client, audit, app) shares the same shape of data instead of
passing around loosely-structured dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class Case:
    """A single troubleshooting case loaded from data/cases.csv."""

    case_id: str
    symptom: str
    topology_note: str
    show_outputs: str
    expected_fault: str
    osi_layer: str
    concept_tag: str
    severity: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RuleResult:
    """The structured output of a single deterministic rule check."""

    rule_id: str
    matched: bool
    title: str
    root_cause: str = ""
    evidence: List[str] = field(default_factory=list)
    osi_layer: str = ""
    severity: str = ""
    suggested_command: str = ""
    suggested_fix: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Diagnosis:
    """The structured diagnosis returned by the AI engine (or the
    deterministic-only fallback when no AI provider is configured)."""

    root_cause: str
    osi_layer: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    next_command: str = ""
    fix_steps: List[str] = field(default_factory=list)
    concept: str = ""
    severity: str = ""
    explanation: str = ""
    deterministic_findings: List[str] = field(default_factory=list)
    caveats: str = ""
    source: str = "deterministic"  # "ai" or "deterministic"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditRecord:
    """One row written to the audit log for every diagnosis + human
    review event."""

    timestamp: str
    case_id: str
    symptom: str
    deterministic_findings: str
    ai_diagnosis: str
    human_action: str
    edited_diagnosis: str = ""
    rejection_reason: str = ""
    confidence: Optional[float] = None
    provider: str = ""

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)
