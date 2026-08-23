# Model Audit Log

## What is logged

Every diagnosis + human review event is appended as one JSON line to
`outputs/audit_log.jsonl` (see `src/audit.py`, `AuditRecord` in
`src/models.py`). Each record contains:

| Field | Description |
|---|---|
| `timestamp` | UTC ISO-8601 timestamp of the review action |
| `case_id` | The case ID, or `(custom)` for ad-hoc evidence |
| `symptom` | The symptom text used for this diagnosis |
| `deterministic_findings` | Summary of every rule that matched (`[rule_id] title`) |
| `ai_diagnosis` | The full diagnosis JSON as generated (AI or deterministic-fallback) |
| `human_action` | One of `approved`, `edited`, `rejected` |
| `edited_diagnosis` | Full JSON of the human-edited diagnosis, if `human_action == edited` |
| `rejection_reason` | Free-text reason, if `human_action == rejected` |
| `confidence` | The diagnosis's confidence score (0.0–1.0) |
| `provider` | `deterministic`, `ai:gemini`, or `human-edited` |

## Why it is logged

1. **Accountability.** Every AI-influenced recommendation that a human
   acted on (or declined to act on) is traceable after the fact.
2. **Model evaluation over time.** Comparing `ai_diagnosis` against
   `edited_diagnosis` on `edited` records shows exactly what a human
   engineer changed and why (via the edit itself plus context), which is
   a direct signal of where the AI layer is weak.
3. **False positive / false negative analysis.** `rejected` records with
   a `rejection_reason` are a curated list of cases where the system's
   output was judged wrong or unhelpful by a human — the highest-value
   data for improving the rule set or the prompt.
4. **Regulatory/operational hygiene.** In a real network operations
   context, being able to show *who/what* approved a change (even a
   recommended one) is a baseline requirement; this project's audit log
   is a lightweight version of that pattern, appropriate for a lab/demo
   environment.

## How human review works

`app.py`'s "Human Review" section presents three actions:

- **APPROVE** — the diagnosis is accepted as-is. Only `human_action =
  approved` is recorded; no command is ever executed by the app.
- **EDIT** — the reviewer can modify the root cause, OSI layer,
  confidence, next command, and fix steps in a form. Both the *original*
  AI/deterministic diagnosis and the *edited* version are stored, so
  nothing is lost.
- **REJECT** — the reviewer records a free-text reason. The diagnosis is
  stored, but flagged as rejected, distinguishing "the AI was wrong"
  cases from "the AI was right but not acted on for other reasons"
  cases (the reason field captures which).

## How false positives / false negatives can be analyzed

Given the JSONL log, an analyst can (for example, in a notebook or a
short script):

```python
import json

records = [json.loads(l) for l in open("outputs/audit_log.jsonl")]
rejected = [r for r in records if r["human_action"] == "rejected"]
edited = [r for r in records if r["human_action"] == "edited"]

# Rejection rate by case_id / by provider
# Diff ai_diagnosis vs edited_diagnosis to see which fields humans changed most
# Correlate low `confidence` scores with rejection/edit rate
```

Because `deterministic_findings` is stored alongside every AI output,
you can also separate "the rule checker was right but the AI's synthesis
was wrong" from "the rule checker itself missed the fault" — the two
have very different fixes (prompt tuning vs. adding/adjusting a rule in
`src/checker.py`).

## How the system can be improved

- **Add more rules** to `src/checker.py` for concepts not yet covered by
  a dedicated rule, using the rejection/edit log to prioritize.
- **Tighten or loosen fuzzy-match sensitivity** in `src/utils.py` if
  `evaluate.py`'s scoring feels too strict or too lenient for your use.
- **Prompt tuning**: adjust `prompts/diagnose_prompt.md` (and the
  in-code system prompt in `src/engine.py`, which must be kept in sync)
  based on patterns seen in `edited`/`rejected` records.
- **Model/provider swap**: because the AI layer is fully abstracted
  behind `src/ai_client.py`, trying a different model or provider is a
  configuration change (`AI_PROVIDER`, `GEMINI_MODEL` /
  `ANTHROPIC_MODEL`), not a code change.
