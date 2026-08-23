# Model Audit Log

## Purpose

NetSage AI maintains an audit trail of diagnosis and human-review decisions.

Every completed review action is recorded as one JSON object per line in:

```text
outputs/audit_log.jsonl
```

The audit implementation is provided by:

```text
src/audit.py
```

The structured audit record is defined through the application's shared models in:

```text
src/models.py
```

The audit log is intended to provide traceability for the diagnostic workflow and to support evaluation of deterministic findings, AI-assisted diagnoses, and human review outcomes.

---

## What Is Logged

Each completed review event is appended to the JSONL audit file.

The record contains information associated with the selected case, the diagnostic output, the review decision, and the source of the diagnosis.

| Field | Description |
|---|---|
| `timestamp` | Timestamp associated with the recorded review action. |
| `case_id` | Identifier of the selected networking case. |
| `symptom` | Symptom text associated with the diagnosis. |
| `deterministic_findings` | Summary of the deterministic rule findings identified for the case. |
| `ai_diagnosis` | The structured diagnosis produced by the diagnostic pipeline, including AI-assisted or deterministic-only output. |
| `human_action` | The final review action: `approved`, `edited`, or `rejected`. |
| `edited_diagnosis` | The edited diagnosis when the reviewer chooses the edit workflow. |
| `rejection_reason` | The reviewer's reason when the recommendation is rejected. |
| `confidence` | Confidence value associated with the recorded diagnosis. |
| `provider` | Indicates whether the diagnosis originated from deterministic processing, Gemini, or a human-edited result. |

The exact record structure is defined by the implementation and should be treated as the source of truth if the implementation changes.

---

## Audit Workflow

The audit process follows the application's human-in-the-loop workflow:

```text
Case
  |
  v
Deterministic Verification
  |
  v
Diagnosis
  |
  v
Engineer Review
  |
  +-------------------+
  |         |         |
  v         v         v
Approve    Edit     Reject
  |         |         |
  +---------+---------+
            |
            v
        Audit Record
            |
            v
outputs/audit_log.jsonl
```

The audit record is created when the reviewer submits a review decision.

---

## Human Review Actions

The application provides three review outcomes.

### Approve

The reviewer accepts the diagnosis as presented.

The audit record stores:

```text
human_action = approved
```

Approval does **not** cause the application to automatically execute Cisco configuration commands.

The system records the approval as a human review decision.

---

### Edit

The reviewer modifies the recommended diagnosis or configuration steps before accepting the result.

The audit record preserves the relevant original diagnosis together with the edited diagnosis.

This allows later analysis of which parts of the recommendation required human correction.

The recorded action is:

```text
human_action = edited
```

---

### Reject

The reviewer rejects the recommendation.

A rejection reason is recorded to provide context for the decision.

The recorded action is:

```text
human_action = rejected
```

The rejection reason can help distinguish between recommendations that were considered incorrect, incomplete, inappropriate, or otherwise unsuitable for acceptance.

---

## Why the Audit Log Is Important

### 1. Accountability and Traceability

The audit log provides a record of what diagnosis was presented and what human review decision was made.

This is particularly important because NetSage AI uses AI as decision support rather than as an autonomous network controller.

---

### 2. Human-AI Agreement Analysis

Edited and rejected records provide information about how often the human reviewer disagrees with or modifies the generated diagnosis.

For example:

```text
AI Diagnosis
     |
     v
Human Review
     |
     +---- Approved
     |
     +---- Edited
     |
     +---- Rejected
```

This can be used to identify areas where the diagnostic pipeline may require improvement.

---

### 3. Deterministic vs AI Analysis

The audit record stores deterministic findings alongside the final diagnosis.

This makes it possible to distinguish between different failure patterns.

For example:

```text
Deterministic finding correct
          +
AI explanation incorrect
          |
          v
Potential AI/prompt issue
```

versus:

```text
Deterministic checker misses fault
          |
          v
Potential rule-engine issue
```

These two situations require different improvements.

---

### 4. Evaluation Over Time

Repeated review decisions can provide useful information for evaluating the diagnostic system.

Edited records can show which fields or recommendations are frequently changed.

Rejected records can reveal recurring weaknesses in the diagnostic logic or AI explanation.

---

## Relationship Between Deterministic Rules and the Audit Log

The deterministic rule checker runs before the AI diagnosis layer.

```text
Case Evidence
     |
     v
Deterministic Rule Checker
     |
     v
Deterministic Findings
     |
     v
Gemini Diagnosis
     |
     v
Human Review
     |
     v
Audit Log
```

Because deterministic findings are retained alongside the diagnosis, the audit history can be used to investigate whether a problem originated in:

- Evidence interpretation
- Deterministic rule matching
- AI explanation or prioritization
- Human review or editing

---

## Example Audit Record Structure

A simplified audit record can be represented as:

```json
{
  "timestamp": "2026-08-23T12:00:00",
  "case_id": "NET-001",
  "symptom": "Example networking symptom",
  "deterministic_findings": [
    "[RULE-001] Example rule finding"
  ],
  "ai_diagnosis": {
    "root_cause": "Example root cause",
    "osi_layer": "Layer 3",
    "confidence": 0.92
  },
  "human_action": "approved",
  "edited_diagnosis": null,
  "rejection_reason": null,
  "confidence": 0.92,
  "provider": "ai:gemini"
}
```

This is an illustrative structure. Actual records are generated by the application.

---

## Inspecting the Audit Log

The audit file can be inspected using any JSONL-compatible tool or a Python script.

For example:

```python
import json

records = []

with open("outputs/audit_log.jsonl", "r", encoding="utf-8") as file:
    for line in file:
        if line.strip():
            records.append(json.loads(line))

print(f"Audit records: {len(records)}")
```

Review actions can then be filtered:

```python
approved = [
    record
    for record in records
    if record["human_action"] == "approved"
]

edited = [
    record
    for record in records
    if record["human_action"] == "edited"
]

rejected = [
    record
    for record in records
    if record["human_action"] == "rejected"
]
```

---

## Analyzing Edited Recommendations

Edited records are particularly useful for identifying where human intervention is required.

A reviewer can compare:

```text
ai_diagnosis
      vs.
edited_diagnosis
```

Possible analysis questions include:

- Which root causes are most frequently changed?
- Which suggested fixes are most frequently edited?
- Are OSI layer classifications being corrected?
- Are confidence values being adjusted?
- Are recommended commands frequently modified?

These observations can guide future improvements to the diagnostic engine and AI prompt.

---

## Analyzing Rejected Recommendations

Rejected records can be grouped by:

- Case ID
- Networking concept
- Severity
- Provider
- Rejection reason

This can help identify recurring weaknesses in the system.

For example:

```text
Many rejections for one networking concept
                |
                v
Investigate deterministic rules
or AI diagnosis behavior
```

A rejection does not automatically prove that the AI was incorrect. The rejection reason and the underlying evidence should be reviewed before deciding what part of the system needs modification.

---

## Improving the System Using Audit Data

Audit records can support several future improvement paths.

### Add or Adjust Deterministic Rules

If repeated cases show that a known fault is not being detected, the deterministic rule set in:

```text
src/checker.py
```

can be expanded or refined.

---

### Improve AI Diagnosis

If deterministic findings are correct but the AI repeatedly misinterprets or poorly prioritizes them, the diagnosis instructions in:

```text
prompts/diagnose_prompt.md
```

and the diagnosis orchestration in:

```text
src/engine.py
```

can be reviewed.

---

### Improve Human Review Analysis

If the system accumulates enough audit records, the review outcomes can be analyzed to identify:

- Common edits
- Common rejection reasons
- Agreement rates
- Problematic networking concepts
- Confidence calibration opportunities

---

## Audit Logging and Deployment

The deployed Streamlit application currently uses the application's JSONL audit mechanism.

The audit log is appropriate for:

- Demonstration
- Internship evaluation
- Local testing
- Single-user or limited-use workflows

For a production multi-user system, the audit layer would be better backed by persistent external storage or a database.

This would provide stronger support for:

- Concurrent users
- Durable storage
- Centralized audit history
- Querying and analytics
- Long-term retention

---

## Relationship to the Dashboard

The application dashboard presents higher-level statistics about the current review session and dataset.

The audit log provides the underlying detailed review records.

Conceptually:

```text
Detailed Audit Records
          |
          v
Review Statistics
          |
          v
Dashboard
```

The dashboard is therefore intended for quick review of aggregate information, while the audit log provides detailed traceability.

---

## Privacy and Security Considerations

The audit log should be treated as application data.

It can contain:

- Networking scenario information
- Diagnostic evidence
- AI-generated diagnosis
- Human review decisions
- Rejection reasons

The Gemini API key is **not** part of the audit record.

API credentials are supplied separately through environment configuration for local development and Streamlit Secrets for the deployed application.

The actual `.env` file and API credentials must not be committed to the GitHub repository.

---

## Current Audit Design

The current audit design follows these principles:

### Append-Only

New review records are appended rather than overwriting previous decisions.

### Human-Centered

Every completed diagnosis must pass through the application's review workflow.

### Traceable

The diagnosis, evidence summary, and review outcome are stored together.

### AI-Aware

The record identifies whether the diagnosis came from deterministic processing, Gemini, or a human-edited result.

### Failure-Tolerant

The audit mechanism is separate from the AI provider, so deterministic-only diagnoses can also be recorded.

---

## Summary

The audit log is an important part of NetSage AI's human-in-the-loop architecture.

The overall relationship is:

```text
Networking Evidence
        |
        v
Deterministic Verification
        |
        v
Gemini-Assisted Diagnosis
        |
        v
Engineer Review
   /      |      \
Approve  Edit   Reject
   \      |      /
        v
   Audit Record
        |
        v
outputs/audit_log.jsonl
```

The audit system does not execute network changes. It records diagnostic and human-review activity so that decisions can be traced, evaluated, and used to improve the system over time.
