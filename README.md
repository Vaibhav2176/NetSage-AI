# NetSage AI

**Network Troubleshooting & Configuration Diagnostic Assistant**

[🚀 Live Demo](https://netsage-ai-by-vaibhav2176a.streamlit.app/) · [🎥 Demo Video](https://github.com/Vaibhav2176/NetSage-AI/blob/main/deliverables/Demo%20Video%20%28NetSage-AI%29.webm)

---

## Overview

NetSage AI is an AI-assisted network troubleshooting and configuration diagnostic platform designed to help engineers and students analyze Cisco/networking problems using structured evidence.

The system follows a **hybrid deterministic + AI approach**:

1. A networking scenario and its Cisco CLI/configuration evidence are provided.
2. A deterministic rule engine analyzes the evidence first.
3. The resulting findings are passed to an AI diagnosis layer when Gemini is configured.
4. Gemini explains and prioritizes the evidence without replacing the deterministic checks.
5. An engineer reviews the diagnosis and can approve, edit, or reject it.
6. The decision is recorded in an audit log.

**The AI is never treated as the sole source of truth.**

The application is designed around a **human-in-the-loop workflow**, where AI provides an explanation and recommendation while the final decision remains with the engineer.

---

## Problem Statement

Diagnosing multi-layer network failures requires analyzing verbose Cisco `show` command output, comparing configuration evidence with the expected topology, and applying networking knowledge across multiple OSI layers.

This process can be time-consuming and error-prone, particularly when troubleshooting a large number of scenarios.

NetSage AI addresses this problem through a hybrid architecture that combines:

- Deterministic rule-based verification
- AI-assisted diagnosis
- Structured evidence
- Human review
- Audit logging

The system is intentionally designed to avoid relying solely on an unconstrained AI model.

---

## Key Features

### 🔎 Scenario Inspection

Allows the reviewer to select and inspect one of the supplied networking scenarios, including:

- Case ID
- Symptom
- Topology notes
- Networking concept
- Severity
- Captured Cisco CLI/show output
- Expected fault

### 🧪 Deterministic Rule Validation

The deterministic rule engine analyzes the supplied evidence before any AI request is made.

The current rule set contains **35 pattern-based troubleshooting rules** covering the supplied networking scenarios.

The rule engine can identify patterns related to areas such as:

- IPv4 addressing
- VLANs
- Trunking
- Inter-VLAN routing
- DHCP
- DNS
- Static routing
- Default routing
- OSPF
- ACLs
- NAT/PAT
- Wireless isolation
- Port security
- HSRP
- IPv6 SLAAC
- CDP
- VTP
- Dynamic ARP Inspection
- RADIUS

Each matching rule produces structured information such as:

- Root cause
- Evidence
- OSI layer
- Severity
- Suggested diagnostic command
- Suggested fix

### 🧠 Gemini-Assisted Diagnosis

When Gemini is configured, NetSage AI sends the application case context and deterministic findings to the Gemini API.

The AI layer is instructed to:

- Explain the deterministic findings
- Prioritize relevant evidence
- Avoid inventing evidence
- Identify the likely root cause
- Identify the relevant OSI layer
- Provide a confidence level
- Suggest the next diagnostic command
- Recommend a potential fix

The response is validated against the application's expected structured diagnosis format.

The application currently uses:

`gemini-3.5-flash-lite`

If Gemini is unavailable, incorrectly configured, or produces invalid output, the application falls back to a clearly identified deterministic-only diagnosis.

---

## Human-in-the-Loop Review

NetSage AI does not automatically execute network configuration commands.

Every diagnosis goes through an engineer review stage.

The reviewer can:

- **Approve & Deploy Fix**
- **Edit Configuration Commands**
- **Reject Recommendation**

Edited recommendations preserve the original diagnosis for traceability.

Rejected recommendations require a reason.

This ensures that AI-generated recommendations are treated as decision support rather than autonomous network changes.

---

## Audit Logging

Every review decision is recorded in an append-only JSONL audit log.

The log records information associated with:

- Case ID
- Diagnosis
- Review decision
- Edited recommendations
- Rejection reasons
- Timestamp
- Review outcome

The audit implementation is provided by:

`src/audit.py`

The detailed audit structure is documented in:

`docs/model_audit_log.md`

For local evaluation, the audit log is stored under:

`outputs/audit_log.jsonl`

For persistent multi-user production deployment, an external database or durable storage backend would be more appropriate.

---

## Dashboard & Statistics

The application includes a dashboard for reviewing dataset and human-review statistics.

The dashboard provides information such as:

- Total dataset cases
- Cases reviewed during the current session
- Accepted recommendations
- Edited recommendations
- Rejected recommendations
- AI-human agreement
- Issue-type distribution
- Severity distribution
- Human review outcomes

These statistics provide a high-level view of the diagnostic and review process.

---

## System Architecture

The overall workflow is:

```text
                  ┌─────────────────────┐
                  │   Network Scenario  │
                  │    + CLI Evidence   │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Deterministic Rule  │
                  │      Checker        │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Structured Findings │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Gemini Diagnosis  │
                  │   (optional layer)  │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Validated Diagnosis │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Engineer Review   │
                  │ Approve / Edit /    │
                  │ Reject              │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │     Audit Log       │
                  └─────────────────────┘
```

Detailed architecture documentation is available in:

`docs/architecture.md`

---

## Project Workflow

The application follows six major stages.

### 1. Scenario Inspection & Human Review Gate

The reviewer selects a case and examines:

- Scenario information
- Topology context
- Expected fault
- Cisco evidence
- Severity
- Networking concept

### 2. Deterministic Rule Validation

The rule checker analyzes the supplied evidence and identifies known fault patterns.

### 3. Diagnosis

The deterministic findings are converted into a structured diagnosis.

When Gemini is configured, the AI layer explains and prioritizes the findings.

### 4. Engineer Verification & Deployment Approval

The engineer reviews the recommendation and can:

- Approve it
- Edit it
- Reject it

No configuration command is automatically executed.

### 5. Dashboard & Statistics

The reviewer can inspect aggregate statistics about:

- Dataset cases
- Issue types
- Severity
- Review outcomes
- AI-human agreement

### 6. Audit History

Review decisions are recorded for traceability and future analysis.

---

## Dataset

The project includes an authoritative dataset containing **30 networking troubleshooting cases**.

The dataset is stored in:

`data/cases.csv`

The cases cover a range of networking concepts including:

- ACL
- DHCP
- DNS
- Gateway
- NAT
- Routing
- VLAN
- Wireless
- OSPF
- Static routing
- Default routing
- Inter-VLAN routing
- Trunking
- Port security
- HSRP
- IPv6 SLAAC
- CDP
- VTP
- Dynamic ARP Inspection
- RADIUS

Each case contains structured scenario information and captured evidence used by the diagnostic pipeline.

---

## Deterministic Checker

The deterministic checker is implemented in:

`src/checker.py`

It normalizes the supplied evidence and applies pattern-based rules to identify known networking faults.

Each rule produces a structured result containing information such as:

- Root Cause
- Evidence
- OSI Layer
- Severity
- Suggested Command
- Suggested Fix

The deterministic layer is deliberately executed before the AI layer.

This provides a reproducible baseline and allows the system to continue operating even when AI functionality is unavailable.

Detailed troubleshooting logic is documented in:

`docs/troubleshooting_logic.md`

---

## AI Layer

The AI integration is implemented through:

- `src/ai_client.py`
- `src/engine.py`
- `prompts/diagnose_prompt.md`

The diagnosis engine provides Gemini with:

- Case information
- Symptom
- Topology context
- Cisco evidence
- Deterministic findings

The AI is instructed to explain and prioritize the supplied evidence rather than invent unsupported findings.

The response is validated before it is displayed by the application.

If the AI request fails or produces invalid output, the application returns a deterministic-only diagnosis instead of crashing.

---

## Gemini Configuration

NetSage AI supports Gemini through environment variables.

### Local Configuration

Create a `.env` file in the project root.

Example:

```env
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "your-gemini-api-key"
GEMINI_MODEL = "gemini-3.5-flash-lite"
AI_TIMEOUT_SECONDS = "30"
```

The actual `.env` file must never be committed to GitHub.

A template is provided as:

`.env.example`

### Streamlit Deployment

For the deployed Streamlit application, Gemini credentials are stored using Streamlit Secrets.

The repository does not contain the actual Gemini API key.

The application reads the same configuration at runtime.

### Deterministic-Only Mode

NetSage AI can also run without Gemini.

If no AI provider is configured, the deterministic rule checker continues to provide the diagnostic findings.

---

## Installation

### Requirements

- Python 3.10 or newer
- pip
- Git

### Clone the Repository

```bash
git clone https://github.com/Vaibhav2176/NetSage-AI.git
cd NetSage-AI
```

### Create a Virtual Environment

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

#### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running Locally

Start the Streamlit application:

```bash
streamlit run app.py
```

The application will normally be available at:

`http://localhost:8501`

If Gemini is being used locally, configure the `.env` file before starting the application.

---

## Deployment

NetSage AI is currently deployed using **Streamlit Community Cloud**.

### Live Application

[https://netsage-ai-by-vaibhav2176a.streamlit.app/](https://netsage-ai-by-vaibhav2176a.streamlit.app/)

### Deployment Configuration

The deployed application uses:

- **Repository:** `Vaibhav2176/NetSage-AI`
- **Branch:** `main`
- **Main file:** `app.py`

Gemini credentials are stored using Streamlit Secrets and are not committed to the GitHub repository.

The deployed application can operate in deterministic-only mode if Gemini is unavailable.

---

## Testing

The project includes automated tests under:

`tests/`

Run the complete test suite using:

```bash
pytest tests/ -v
```

The repository currently contains **31 automated tests**. The result below is the documented baseline; it does not claim a newly executed test run.

The tests cover areas including:

- CSV loading and validation
- Case lookup
- Deterministic rule checking
- Major networking rule categories
- Malformed evidence handling
- Diagnosis generation
- AI response validation
- AI fallback behavior

### Current Test Result

```text
Documented baseline: 31/31 tests passing
```

---

## Evaluation

The project includes an evaluation script:

`evaluate.py`

Run it with:

```bash
python evaluate.py
```

The evaluator runs the deterministic checker against all **30 supplied cases** and compares the resulting findings against each case's expected fault.

### Current Evaluation Result

```text
Total cases: 30
Correct deterministic detections: 30
Missed: 0
Mismatched: 0
Accuracy: 100.0%
```

The deterministic evaluation provides a reproducible baseline independent of the Gemini API.

---

## Current Project Status

The current implementation includes:

- ✅ 30 supplied networking cases
- ✅ Deterministic rule validation
- ✅ 35 troubleshooting rules
- ✅ 30/30 deterministic evaluation accuracy
- ✅ Documented baseline: 31/31 automated tests passing
- ✅ Gemini-assisted diagnosis
- ✅ Structured AI response validation
- ✅ Deterministic fallback when AI is unavailable
- ✅ Human-in-the-loop review
- ✅ Approve / Edit / Reject workflow
- ✅ Audit logging
- ✅ Dashboard and statistics
- ✅ Streamlit deployment
- ✅ Secure Gemini API configuration through Streamlit Secrets

---

## Security

The Gemini API key is not stored in the source code or GitHub repository.

Local development uses:

`.env`

which is excluded through:

`.gitignore`

The repository only contains:

`.env.example`

as a configuration template.

For Streamlit deployment, secrets are stored through the platform's encrypted Secrets configuration.

No Cisco configuration command is automatically executed by the application.

---

## Human-in-the-Loop Design

The application intentionally separates:

```text
Detection
   ↓
AI Explanation
   ↓
Human Review
   ↓
Final Decision
```

This design reduces the risk of treating an AI-generated recommendation as an automatically trusted network configuration.

The application only provides recommendations.

An engineer must review the recommendation before it is considered actionable.

---

## Limitations

The current implementation has several limitations:

- The deterministic rule set is tuned primarily to the vocabulary and evidence patterns represented in the supplied 30-case dataset and common Cisco IOS phrasing.
- It is not a complete Cisco configuration parser.
- Faults phrased substantially differently from the supported patterns may not be detected by the deterministic checker.
- The AI diagnosis layer depends on an external Gemini API.
- Provider outages, rate limits, or configuration errors can prevent AI-assisted diagnosis.
- The application falls back to deterministic diagnosis when AI functionality is unavailable.
- The audit log currently uses local JSONL storage and is not designed as a multi-user production database.
- The evaluation comparison is heuristic rather than semantic or embedding-based.

---

## Future Improvements

Potential future improvements include:

- Expanding the deterministic rule library as additional fault patterns are identified.
- Adding more networking troubleshooting cases.
- Introducing a persistent database for multi-user audit logging.
- Improving confidence calibration using historical human review outcomes.
- Expanding automated evaluation and regression testing.
- Adding more structured network configuration parsing.
- Improving long-term audit analytics.

---

## Project Structure

```text
NetSage-AI/
│
├── app.py
├── evaluate.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
│
├── data/
│   └── cases.csv
│
|──deliverables/
│   ├── diagnose_prompt.md
│   ├── responsible_ai_log.md
│   ├── dashboard_statistics.xlsx
    ├── Demo Video (NetSage-AI).webm
│   └── checker/
│       ├── checker.py
│       └── sample_output.txt
|
├── src/
│   ├── __init__.py
│   ├── checker.py
│   ├── engine.py
│   ├── models.py
│   ├── case_loader.py
│   ├── ai_client.py
│   ├── audit.py
│   └── utils.py
│
├── prompts/
│   └── diagnose_prompt.md
│
├── docs/
│   ├── architecture.md
│   ├── troubleshooting_logic.md
│   ├── model_audit_log.md
│   └── user_guide.md
│
├── tests/
│   ├── test_checker.py
│   ├── test_case_loader.py
│   └── test_engine.py
│
└── outputs/
    └── .gitkeep
```

---

## Documentation

Additional project documentation is available in the `docs/` directory.

### Architecture

`docs/architecture.md`

Describes the overall system architecture and module responsibilities.

### Troubleshooting Logic

`docs/troubleshooting_logic.md`

Describes the deterministic rule catalogue and matching logic.

### Model Audit Log

`docs/model_audit_log.md`

Describes the audit log fields and guidance for analyzing review outcomes.

### User Guide

`docs/user_guide.md`

Provides instructions for running and evaluating the application.

---

## Design Principles

NetSage AI is built around the following principles:

### Evidence First

The system prioritizes supplied networking evidence instead of relying solely on generated assumptions.

### Deterministic Verification

Known networking fault patterns are checked using reproducible rules before AI diagnosis is requested.

### AI as an Assistant

Gemini provides explanation and prioritization rather than acting as the sole diagnostic authority.

### Human Oversight

An engineer reviews every diagnosis before it is considered actionable.

### Safe Failure

If the AI provider is unavailable or produces invalid output, the deterministic diagnostic layer remains available.

### Traceability

Human review decisions are recorded in the audit log.

---

## License

This project was developed as part of a Cisco virtual internship project.
