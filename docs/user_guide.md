# User Guide

## 1. Introduction

NetSage AI is a network troubleshooting and configuration diagnostic assistant. It is designed to help a reviewer examine networking scenarios, validate Cisco evidence using deterministic rules, and, when Gemini is configured, generate an AI-assisted diagnosis.

The application follows a human-in-the-loop process. The system provides findings and recommendations, but it does not automatically execute Cisco configuration commands. The reviewer makes the final decision by approving, editing, or rejecting the recommendation.

The project contains 30 networking troubleshooting cases and can also be run without Gemini in deterministic-only mode.

---

## 2. Opening NetSage AI

### Live Application

The deployed application is available at:

https://netsage-ai-by-vaibhav2176a.streamlit.app/

Open the link in a browser to use the deployed version.

### Running Locally

To run the application on a local machine, first install the project dependencies and then run:

```bash
streamlit run app.py
```

Streamlit normally provides a local address similar to:

```text
http://localhost:8501
```

Open that address in a browser.

---

## 3. Gemini Configuration

Gemini is optional. The deterministic troubleshooting functionality does not require an API key.

### Local Configuration

For local use, create a `.env` file in the project root using `.env.example` as the template.

Example:

```env
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "your-gemini-api-key"
GEMINI_MODEL = "gemini-3.5-flash-lite"
AI_TIMEOUT_SECONDS = "30"
```

The actual API key should only be placed in the local `.env` file.

Do not commit `.env` to GitHub.

### Deployed Configuration

The deployed Streamlit application uses Streamlit Secrets for the Gemini configuration.

The required values are configured in the application's Secrets settings rather than being stored in the GitHub repository.

The deployed application currently uses:

```text
AI_PROVIDER = gemini
GEMINI_MODEL = gemini-3.5-flash-lite
```

The Gemini API key itself is not included in the source code or repository.

### If Gemini Is Not Available

The application remains usable without Gemini.

In that situation:

```text
Case
  ↓
Deterministic Rule Validation
  ↓
Deterministic Diagnosis
  ↓
Human Review
```

No Gemini request is made, and the application clearly indicates that the diagnosis is deterministic-only.

---

## 4. Main Application Interface

The application is organized around the complete troubleshooting and review workflow.

The main stages are:

1. Scenario Inspection & Human Review Gate
2. Deterministic Rule Validation
3. Diagnosis
4. Engineer Verification & Deployment Approval
5. Dashboard & Statistics
6. Audit History

The sidebar is used for scenario selection and optional evidence changes.

---

## 5. Sidebar

### Scenario Selection

Use **Scenario Selection** to choose one of the 30 supplied networking cases.

Each case has its own:

- Case ID
- Symptom
- Topology information
- Networking concept
- Severity
- Cisco evidence
- Expected fault

Selecting a case updates the information shown in the main application.

---

### Advanced Evidence Override

The **Advanced Evidence Override** option can be used when testing or experimenting with different evidence.

It allows the reviewer to replace or modify selected case information such as:

- Symptom
- Topology information
- Cisco evidence

This is useful for testing how the deterministic checker and diagnosis workflow respond to different evidence.

For normal evaluation of the supplied dataset, use the original case information.

---

### Gemini AI Status

The Gemini status indicator shows whether the application has access to the configured Gemini provider.

If Gemini is configured correctly, the AI diagnosis stage can be used.

If Gemini is not available, the application continues in deterministic-only mode.

---

# 6. Dashboard Workflow

## 6.1 Scenario Inspection & Human Review Gate

This is the first stage of the troubleshooting process.

After selecting a case, review the information presented for the scenario.

The section provides information such as:

- Case ID
- Symptom
- Topology Note
- Networking Concept
- Severity
- Expected Root Cause / Expected Fault
- Captured Cisco Show Output

The Cisco evidence is particularly important because it is the information used by the deterministic checker and provided as context to the AI diagnosis layer.

### What to look for

Before running the diagnosis, read the symptom and the Cisco evidence.

For example, evidence may contain output indicating:

```text
interface is administratively down
```

That information can provide a strong indication of the type of networking problem being investigated.

---

## 6.2 Deterministic Rule Validation

The deterministic rule checker examines the supplied evidence before the Gemini diagnosis is generated.

It looks for known networking fault patterns using the project's rule library.

The result is displayed under **Deterministic Rule Validation**.

A successful validation can show information such as:

```text
{
    "status": "CHECKS_PASSED",
    "flagged_issues": [...]
}
```

or findings that identify a matching fault pattern.

### Why this stage matters

This stage provides the evidence-based baseline for the diagnosis.

The AI does not replace these checks. When Gemini is used, its job is to explain and prioritize the information already available from the case and deterministic findings.

---

## 6.3 Diagnosis

The **Diagnosis** section provides the diagnostic conclusion.

When Gemini is configured, use:

**Generate Diagnosis**

The application prepares the selected case and deterministic findings and sends the relevant context to Gemini.

The resulting diagnosis contains information such as:

- Root Cause
- OSI Layer
- Confidence
- Evidence
- Next Diagnostic Command
- Suggested Fix

### Root Cause

Describes the most likely reason for the observed networking problem.

### OSI Layer

Identifies the relevant OSI layer associated with the diagnosis.

### Confidence

Indicates how confident the diagnosis is in the identified cause.

### Evidence

Lists the information from the case that supports the diagnosis.

### Next Diagnostic Command

Provides a Cisco command that can be used to investigate or verify the suspected problem further.

### Suggested Fix

Provides recommended Cisco configuration steps or actions that may resolve the issue.

These are recommendations only. The application does not execute them automatically.

---

## 6.4 Engineer Verification & Deployment Approval

After reviewing the diagnosis, the reviewer must decide how to proceed.

The application provides three review options:

### Approve & Deploy Fix

Use this when the reviewer agrees with the recommendation.

The decision is recorded as an approved review.

Despite the label, the application itself does not execute the Cisco commands. The action represents the engineer's approval of the proposed fix.

### Edit Configuration Commands

Use this when the diagnosis is generally useful but the recommended commands or other diagnosis details need to be changed.

The edited result is recorded along with the original diagnosis so that the change can be reviewed later.

### Reject Recommendation

Use this when the recommendation should not be accepted.

A rejection requires a reason.

The rejection and the reason are recorded in the audit history.

---

# 7. Dashboard & Statistics

The dashboard provides a higher-level view of the dataset and the current review session.

Depending on the current session, the dashboard can show:

- Total Dataset Cases
- Reviewed This Session
- Accepted
- Edited
- Rejected
- AI-Human Agreement
- Issue Types in the Dataset
- Severity Distribution
- Case-by-case review information

These statistics are intended to provide a quick overview of the diagnostic and human-review activity.

### Issue Types

The issue-type statistics show how the 30 supplied cases are distributed across networking concepts such as routing, VLAN, DHCP, DNS, ACL, NAT, wireless, and other supported areas.

### Severity Distribution

The severity statistics show how the cases are distributed across their assigned severity levels.

### AI-Human Agreement

This statistic provides an indication of how often the human review outcome agrees with the diagnosis presented by the system.

It should be interpreted as a review statistic rather than as a general measure of AI accuracy.

---

# 8. Audit History

Every submitted human review decision is recorded in the application's audit log.

The local audit file is:

```text
outputs/audit_log.jsonl
```

The audit history allows the reviewer to trace decisions made during the diagnostic workflow.

Records can include:

- Case ID
- Symptom
- Deterministic findings
- Diagnosis
- Human action
- Edited diagnosis
- Rejection reason
- Confidence
- Provider
- Timestamp

The audit log is designed to support traceability and evaluation of the system.

For more information about the audit structure, see:

```text
docs/model_audit_log.md
```

---

# 9. Demonstrating NET-001

NET-001 can be used as a simple demonstration of the complete workflow.

### Step 1 — Select the Case

In the sidebar, select:

```text
NET-001
```

### Step 2 — Inspect the Scenario

Review the symptom, topology note, concept, severity, and captured Cisco evidence.

Pay particular attention to the interface status shown in the Cisco output.

### Step 3 — Run Verification

Use the verification control to run the deterministic checks.

Review the findings displayed under **Deterministic Rule Validation**.

### Step 4 — Generate the Diagnosis

If Gemini is configured, select:

**Generate Diagnosis**

The application will use the case context and deterministic findings to produce the structured diagnosis.

### Step 5 — Review the Diagnosis

Check:

- Root Cause
- OSI Layer
- Confidence
- Evidence
- Next Diagnostic Command
- Suggested Fix

### Step 6 — Make a Human Decision

Choose one of:

- **Approve & Deploy Fix**
- **Edit Configuration Commands**
- **Reject Recommendation**

If rejecting the recommendation, provide a reason.

### Step 7 — Check the Audit History

Open the audit history and verify that the review decision has been recorded.

This demonstrates the complete:

```text
Scenario
   ↓
Deterministic Verification
   ↓
Diagnosis
   ↓
Human Review
   ↓
Audit
```

workflow.

---

# 10. Deterministic-Only Mode

Gemini is not required for the application to function.

If `GEMINI_API_KEY` is missing or Gemini is unavailable, the system continues to use the deterministic rule checker.

The workflow becomes:

```text
Case
  ↓
Deterministic Rule Validation
  ↓
Deterministic Diagnosis
  ↓
Human Review
  ↓
Audit History
```

In this mode:

- No Gemini API call is made.
- Deterministic findings are still displayed.
- The diagnosis remains available.
- Human review remains available.
- Audit logging remains available.

This fallback behavior ensures that an external AI service failure does not make the entire application unusable.

---

# 11. Testing the Project

The project contains an evaluation script and automated tests.

## Evaluation

Run:

```bash
python evaluate.py
```

The evaluation checks the deterministic diagnostic output against the expected faults for all 30 supplied cases.

The current evaluation result is:

```text
30/30 cases matched
100.0% deterministic evaluation accuracy
```

This evaluation does not require the Gemini API.

---

## Automated Tests

Run:

```bash
pytest tests/ -v
```

The current test suite contains:

```text
31 tests
```

The tests cover areas including:

- Case loading and validation
- Case lookup
- Deterministic rule checking
- Major rule categories
- Malformed evidence handling
- Diagnosis generation
- AI response validation
- AI fallback behavior

Current result:

```text
31/31 tests passing
```

---

# 12. Troubleshooting Common Problems

## The application does not start

Make sure the project dependencies are installed:

```bash
pip install -r requirements.txt
```

Then run:

```bash
streamlit run app.py
```

---

## Gemini diagnosis is not available

Check that the Gemini configuration is present.

For local use, verify the `.env` configuration.

For the deployed application, verify the Streamlit Secrets configuration.

The application can still be used in deterministic-only mode if Gemini is unavailable.

---

## Gemini API errors appear

Check:

- The API key is valid.
- The Gemini model name is correct.
- The application has access to the internet.
- The configured Gemini service is available.
- The provider has not reached its applicable rate or usage limit.

The application should fall back to deterministic diagnosis when the AI request cannot be completed.

---

## The selected case does not appear correctly

Check that the project is using the supplied:

```text
data/cases.csv
```

Do not modify the dataset when carrying out the standard 30-case evaluation.

---

## Audit history is empty

An audit entry is created after a human review action is submitted.

Simply generating a diagnosis does not represent a completed human review.

Use one of:

- Approve & Deploy Fix
- Edit Configuration Commands
- Reject Recommendation

and submit the decision.

---

# 13. Recommended Evaluation Procedure

For an evaluator who is using NetSage AI for the first time, the following sequence is recommended:

1. Open the live application.
2. Select one of the 30 cases.
3. Read the scenario information and Cisco evidence.
4. Run the deterministic verification.
5. Review the flagged findings.
6. Generate the diagnosis with Gemini enabled.
7. Compare the AI diagnosis with the deterministic findings.
8. Review the root cause, evidence, OSI layer, confidence, command, and suggested fix.
9. Make a human review decision.
10. Open the audit history and verify the decision.
11. Open the dashboard and review the session statistics.

This sequence demonstrates the main purpose of the project without requiring any Cisco configuration to be executed.

---

# 14. Important Safety and Usage Notes

### No Automatic Cisco Configuration

NetSage AI does not connect to a Cisco device and does not automatically execute the suggested commands.

The commands shown by the application are recommendations for the engineer to verify and apply separately if appropriate.

### Evidence Matters

The diagnosis should always be interpreted in the context of the supplied symptom, topology, and Cisco evidence.

### AI Is an Assistant

Gemini provides explanation and prioritization. It should not be treated as an independent source of truth.

### Human Review Is Required

The final decision is made through the application's human review workflow.

### Protect API Credentials

Never commit:

```text
.env
```

or an actual Gemini API key to GitHub.

For the deployed application, use Streamlit Secrets.

---

# 15. Quick Reference

| Task | Action |
|---|---|
| Open deployed application | Visit the Streamlit live URL |
| Run locally | `streamlit run app.py` |
| Select a case | Use Scenario Selection |
| Test different evidence | Use Advanced Evidence Override |
| Check network evidence | Review Deterministic Rule Validation |
| Generate AI diagnosis | Select Generate Diagnosis |
| Accept recommendation | Approve & Deploy Fix |
| Modify recommendation | Edit Configuration Commands |
| Reject recommendation | Reject Recommendation + provide reason |
| View review records | Open Audit History |
| View statistics | Open Dashboard & Statistics |
| Run evaluation | `python evaluate.py` |
| Run tests | `pytest tests/ -v` |

---

# 16. Related Documentation

The project contains additional technical documentation:

### Architecture

```text
docs/architecture.md
```

Describes the system architecture, data flow, module responsibilities, AI integration, deterministic-first design, and failure handling.

### Troubleshooting Logic

```text
docs/troubleshooting_logic.md
```

Describes the deterministic troubleshooting rules and how network evidence is matched to known fault patterns.

### Model Audit Log

```text
docs/model_audit_log.md
```

Describes the audit record, human-review decisions, and how audit information can be used for evaluation and improvement.

---

# 17. Live Application

The current deployed version of NetSage AI is available at:

https://netsage-ai-by-vaibhav2176a.streamlit.app/

The deployed application uses:

```text
Repository: Vaibhav2176/NetSage-AI
Branch: main
Entry point: app.py
AI provider: Google Gemini
Model: gemini-3.5-flash-lite
```

The Gemini API key is provided to the deployed application through Streamlit Secrets and is not stored in the GitHub repository.
