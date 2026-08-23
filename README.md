# NetSage AI

**Network Troubleshooting & Configuration Diagnostic Assistant**

## Overview

NetSage AI is an AI-assisted Cisco/network troubleshooting application.
It takes a networking problem and Cisco CLI/configuration evidence, runs
deterministic rule-based checks first, then (optionally) uses an AI
model to explain the likely root cause, evidence, OSI layer, confidence,
next diagnostic command, and recommended fix — with mandatory human
review before anything is considered "actionable."

**The AI is never the sole source of truth.** It recommends; a human
approves, edits, or rejects; every decision is logged.

## Problem statement

Diagnosing multi-layer network failures (in Cisco Packet Tracer labs or
real environments) requires reading verbose `show` command output,
cross-referencing config against expected topology, and applying
expert-level pattern recognition across OSI layers — a slow, error-prone
process for students and operators when configuration changes are applied without verification. NetSage AI narrows that gap
with a hybrid deterministic + AI pipeline and a human-in-the-loop gate,
rather than either a rigid rule engine alone or an unconstrained LLM.

## Features

- 30-case authoritative dataset (`data/cases.csv`) covering IPv4
  addressing, VLANs/trunking, inter-VLAN routing, DHCP (+relay + pool
  exhaustion), DNS, static/default routing, OSPF, ACLs, NAT/PAT, guest
  wireless isolation, port security, HSRP, IPv6 SLAAC, CDP, VTP, DAI,
  and RADIUS.
- Deterministic, regex-based rule checker (`src/checker.py`, 34 rules)
  that runs before any AI call and works even with zero AI configured.
- AI diagnosis layer using Google Gemini that explains and prioritizes deterministic findings via a strict JSON schema.
- Malformed/missing AI output is caught and gracefully falls back to a
  clearly labeled deterministic-only diagnosis — the app never crashes.
- Full human-in-the-loop workflow: Approve / Edit / Reject.
- Append-only JSONL audit log of every diagnosis + review decision.
- `evaluate.py` compares deterministic findings with the expected fault for all 30 cases.
- 31 unit tests (`pytest tests/`).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full pipeline
diagram (Mermaid + ASCII) and module responsibility table. Summary:

```
case/evidence -> deterministic checker -> structured findings
              -> AI diagnosis (or deterministic fallback) -> validated JSON
              -> human review (approve/edit/reject) -> audit log
```

## Installation

Requires Python 3.10+.

```bash
git clone <this-repo>
cd NetSage-AI
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment variables

Copy `.env.example` to `.env` and fill in only what you need:

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `gemini` or blank for deterministic-only mode |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Used when `AI_PROVIDER=gemini` |
| `AI_TIMEOUT_SECONDS` | Timeout applied to the AI provider call |

The app works fully without any of these set — it just won't produce an
AI-synthesized diagnosis, only the deterministic one.


## Gemini configuration

NetSage can run fully without an API key. When `AI_PROVIDER=gemini` and
`GEMINI_API_KEY` are configured, the diagnosis engine sends the application
case context and deterministic findings to the Gemini API and validates the
returned JSON before displaying it.

The project defaults to `gemini-3.5-flash-lite`. Gemini offers a free tier
for supported models subject to current rate limits. No API key is stored
in this repository.

## Project Workflow

The application follows a six-stage workflow:

1. **Scenario Inspection & Human Review Gate** — review the selected case,
   topology context, expected fault, and captured Cisco show output.
2. **Deterministic Rule Validation** — identify known network configuration or
   connectivity findings from the supplied evidence.
3. **Diagnosis** — combine the deterministic findings with Gemini-assisted
   explanation when Gemini is configured.
4. **Engineer Verification & Deployment Approval** — an engineer approves,
   edits, or rejects the recommendation.
5. **Dashboard & Statistics** — review case coverage, issue types, severity,
   and human review outcomes.
6. **Audit History** — retain review decisions for evaluation and traceability.

## Running locally

```bash
streamlit run app.py
```

Then open the printed local URL (typically `http://localhost:8501`).

## How the deterministic checker works

`src/checker.py` runs ~34 pattern-matching rules against the combined
symptom + topology note + Cisco evidence text (normalized for
whitespace/case). Every matching rule is returned as a `RuleResult` with
its own root cause, evidence snippet, OSI layer, severity, suggested
command, and suggested fix. See
[`docs/troubleshooting_logic.md`](docs/troubleshooting_logic.md) for the
full rule catalogue and matching logic.

## How the AI layer works

`src/engine.py` builds an application case context (documented in full in
[`prompts/diagnose_prompt.md`](prompts/diagnose_prompt.md)) that includes
the case evidence *and* the deterministic findings, instructing the
model to explain/prioritize rather than invent evidence, and to return
strict JSON matching a fixed schema. `src/ai_client.py` abstracts the
actual Gemini API call and attempts safe JSON
recovery if the model's response isn't perfectly clean JSON. If the AI
is unavailable or its output can't be validated, the engine returns a
deterministic-only `Diagnosis` instead of failing.

## Human-in-the-loop process

Every diagnosis — AI-generated or deterministic-only — must be
Approved, Edited, or Rejected in the UI before it's considered final.
Editing preserves both the original and edited versions; rejecting
requires a reason. No Cisco configuration command is ever executed by
this application; it only displays recommendations.

## Audit logging

Every review decision is appended as one line of JSON to
`outputs/audit_log.jsonl` (see `src/audit.py`). See
[`docs/model_audit_log.md`](docs/model_audit_log.md) for the full field
reference and guidance on analyzing false positives/negatives over time.

## Testing

```bash
pytest tests/ -v
```

Covers CSV loading/validation, case lookup, each major rule category,
malformed-evidence handling, and AI JSON validation/fallback behavior
(31 tests, all passing as of this build).

## Evaluation

```bash
python evaluate.py
```

Runs the deterministic checker against all 30 cases and fuzzy-compares
the top finding to each case's `expected_fault`. **Actual result on this
build: 28/30 correct (93.3%), 0 missed entirely, 2 near-miss on wording**
— see [`docs/troubleshooting_logic.md`](docs/troubleshooting_logic.md)
for the two wording-based misses and why they still produce a relevant
finding.

## Deployment (Streamlit Cloud)

1. Push this repository to GitHub (ensure `.env` is **not** committed —
   it's in `.gitignore`).
2. In Streamlit Cloud, create a new app pointing at `app.py` on your
   branch.
3. Under the app's **Settings → Secrets**, add the same keys as
   `.env.example` (e.g. `AI_PROVIDER = "gemini"`,
   `GEMINI_API_KEY = "your-gemini-key"`). Streamlit Cloud exposes these as
   environment variables, which `app.py`/`src/ai_client.py` read the
   same way as a local `.env`.
4. Deploy. The app works immediately in deterministic-only mode even
   before secrets are configured.

## Limitations

- The deterministic rule set is tuned for the vocabulary in the supplied
  30-case dataset and common Cisco IOS phrasing; it is not a general
  Cisco config parser and can miss faults phrased very differently from
  what it expects.
- The AI layer depends on an external API; network/provider outages
  degrade the app to deterministic-only mode rather than blocking it.
- The audit log is a local JSONL file, suitable for a single-user local
  or small-team Streamlit Cloud deployment — not a multi-writer
  production datastore.
- Fuzzy matching in `evaluate.py` is a heuristic (token overlap +
  sequence similarity), not a semantic/embedding-based comparison.

## Future improvements

- Add more deterministic rules as new fault patterns are observed in
  rejected/edited audit records (see
  [`docs/model_audit_log.md`](docs/model_audit_log.md)).
- Add a lightweight database backend if multi-user concurrent audit
  logging becomes necessary.
- Add confidence calibration by comparing AI confidence scores against
  actual human approve/edit/reject outcomes over time.
- Expand the deterministic rule library as new troubleshooting patterns are added.

## Project structure

```
NetSage-AI/
├── app.py
├── evaluate.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── data/
│   └── cases.csv
├── src/
│   ├── __init__.py
│   ├── checker.py
│   ├── engine.py
│   ├── models.py
│   ├── case_loader.py
│   ├── ai_client.py
│   ├── audit.py
│   └── utils.py
├── prompts/
│   └── diagnose_prompt.md
├── docs/
│   ├── architecture.md
│   ├── troubleshooting_logic.md
│   ├── model_audit_log.md
│   └── user_guide.md
├── tests/
│   ├── test_checker.py
│   ├── test_case_loader.py
│   └── test_engine.py
└── outputs/
    └── .gitkeep
```
