"""
src/audit.py

Simple, dependency-free audit logging using JSON Lines (JSONL).

Each line in outputs/audit_log.jsonl is one AuditRecord. JSONL was
chosen over a database because:
- It's human-readable and diffable.
- It's append-only, matching how an audit trail should behave.
- It needs zero extra infrastructure, which matters for a project meant
  to run locally and on Streamlit Cloud.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from src.models import AuditRecord, Diagnosis, RuleResult

DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "outputs" / "audit_log.jsonl"


def _findings_summary(findings: List[RuleResult]) -> str:
    if not findings:
        return "(no deterministic findings)"
    return "; ".join(f"[{f.rule_id}] {f.title}" for f in findings)


def append_record(
    case_id: str,
    symptom: str,
    findings: List[RuleResult],
    diagnosis: Diagnosis,
    human_action: str,
    edited_diagnosis: Optional[Diagnosis] = None,
    rejection_reason: str = "",
    log_path: Optional[Path] = None,
) -> AuditRecord:
    """Append one audit event and return the record that was written.

    Never raises on I/O errors that would crash the Streamlit app; the
    caller should check the return value / wrap in try/except if it
    needs to surface a write failure to the user.
    """
    path = log_path or DEFAULT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    provider = ""
    if diagnosis and diagnosis.source:
        provider = diagnosis.source

    record = AuditRecord(
        timestamp=AuditRecord.now_iso(),
        case_id=case_id or "(custom)",
        symptom=symptom,
        deterministic_findings=_findings_summary(findings),
        ai_diagnosis=json.dumps(diagnosis.to_dict()) if diagnosis else "",
        human_action=human_action,
        edited_diagnosis=json.dumps(edited_diagnosis.to_dict()) if edited_diagnosis else "",
        rejection_reason=rejection_reason,
        confidence=diagnosis.confidence if diagnosis else None,
        provider=provider,
    )

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict()) + "\n")

    return record


def read_records(log_path: Optional[Path] = None, limit: Optional[int] = None) -> List[dict]:
    """Read all audit records, most recent first."""
    path = log_path or DEFAULT_LOG_PATH
    if not path.exists():
        return []

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    records.reverse()  # most recent first
    if limit is not None:
        records = records[:limit]
    return records


def clear_log(log_path: Optional[Path] = None) -> None:
    """Remove all audit records. Used only for tests / manual reset."""
    path = log_path or DEFAULT_LOG_PATH
    if path.exists():
        path.unlink()
