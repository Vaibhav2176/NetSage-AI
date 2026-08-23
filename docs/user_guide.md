# User Guide

## 1. Launching the app

```bash
streamlit run app.py
```

Open the local Streamlit URL, normally `http://localhost:8501`.

## 2. Gemini configuration

For local use, copy `.env.example` to `.env` and set:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The application still works without a key; it falls back to deterministic diagnosis.

For Streamlit deployment, place the same values in the app's Secrets settings.
Never commit `.env` or an API key.

## 3. Sidebar

- **Scenario Selection** — choose one of the 30 cases.
- **Advanced Evidence Override** — optionally replace the symptom,
  topology, or Cisco evidence for experiments.
- **Gemini AI Status** — shows whether the Gemini key is configured.

## 4. Dashboard workflow

### 1. Scenario Inspection & Human Review Gate
Shows the selected case, symptom, topology, expected fault, OSI layer,
concept, severity, and Cisco show output.

### 2. Deterministic Rule Validation
The rule engine examines the evidence and reports matching network
fault patterns before the AI call.

### 3. Diagnosis
Click **Generate Diagnosis**. Gemini receives the application
case context and deterministic findings and returns a structured
diagnosis containing:

- root cause
- OSI layer
- confidence
- evidence
- next diagnostic command
- suggested fix

If Gemini is unavailable, the deterministic result is clearly labeled
and displayed instead.

### 4. Engineer Verification & Deployment Approval

The reviewer can:

- Approve the recommendation
- Edit the recommendation
- Reject it with a reason

The application never executes Cisco commands.

### 5. Dashboard & Statistics

The dashboard summarizes:

- total dataset cases
- reviewed cases
- approved / edited / rejected outcomes
- human acceptance rate
- issue-type distribution
- severity distribution
- automated verification coverage
- case-by-case coverage table

### 6. Audit History

Every review is stored in `outputs/audit_log.jsonl` and displayed in
the audit history section.

## 5. Demonstrating NET-001

1. Select `NET-001`.
2. Review the Cisco evidence showing the administratively-down interface.
3. Run verification.
4. Click **Generate Diagnosis** when a Gemini key is configured.
5. Review the root cause, evidence, next command, and fix.
6. Approve, edit, or reject the recommendation.
7. Review the resulting audit record.

## 6. Deterministic-only mode

If `GEMINI_API_KEY` is missing, the application remains usable.
The rule checker produces the first-pass diagnosis and the UI explains
that no Gemini call was made.

## 7. Testing

```bash
python evaluate.py
pytest tests/ -v
```
