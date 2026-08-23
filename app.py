"""
NetSage AI — Network Troubleshooting & Configuration Diagnostic Assistant.

Workflow:
1. Scenario Inspection & Human Review Gate
2. Deterministic Rule Validation
3. Diagnosis
4. Engineer Verification & Deployment Approval
5. Dashboard & Statistics
6. Audit History

NetSage provides recommendations only. It does not execute Cisco commands.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.ai_client import AIClient
from src.audit import append_record, read_records
from src.case_loader import CaseLoadError, load_cases
from src.checker import run_checker
from src.engine import diagnose
from src.models import Diagnosis


st.set_page_config(
    page_title="NetSage AI",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = Path(__file__).resolve().parent / "data" / "cases.csv"


# ---------------------------------------------------------------------------
# Page styling
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1350px;
        padding-top: 2.2rem;
        padding-bottom: 3.5rem;
    }

    .netsage-title {
        font-size: 2.05rem;
        font-weight: 750;
        color: #172b4d;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }

    .hero-badge {
        display: inline-block;
        padding: 0.28rem 0.65rem;
        border-radius: 999px;
        background: #eef4ff;
        color: #2457a6;
        font-size: 0.76rem;
        font-weight: 650;
        margin-bottom: 0.75rem;
        border: 1px solid #d8e5ff;
    }

    .netsage-subtitle {
        color: #667085;
        font-size: 0.95rem;
        line-height: 1.55;
        max-width: 900px;
        margin-bottom: 1.8rem;
    }

    .section-title {
        margin-top: 2.45rem;
        margin-bottom: 0.3rem;
        color: #172b4d;
        font-size: 1.35rem;
        font-weight: 720;
    }

    .section-rule {
        height: 3px;
        width: 46px;
        border-radius: 4px;
        background: linear-gradient(90deg, #4f46e5, #38bdf8);
        margin-bottom: 0.75rem;
    }

    .section-description {
        color: #667085;
        font-size: 0.88rem;
        line-height: 1.55;
        margin-bottom: 1.15rem;
    }


    .diagnosis-card {
        border: 1px solid #d9e2ec;
        border-radius: 12px;
        background: linear-gradient(135deg, #f8fbff 0%, #f4f7fc 100%);
        padding: 1.1rem 1.15rem;
        min-height: 145px;
        box-shadow: 0 4px 16px rgba(16, 24, 40, 0.045);
    }

    .diagnosis-label {
        color: #344054;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .diagnosis-value {
        color: #101828;
        margin-top: 0.6rem;
        font-size: 0.98rem;
        line-height: 1.6;
    }

    .small-note {
        color: #667085;
        font-size: 0.82rem;
        line-height: 1.5;
    }

    .metric-strip {
        border: 1px solid #e6eaf0;
        border-radius: 14px;
        padding: 0.75rem 0.8rem 0.25rem 0.8rem;
        background: linear-gradient(180deg, #fbfcff 0%, #ffffff 100%);
        box-shadow: 0 4px 16px rgba(16, 24, 40, 0.035);
        margin-bottom: 0.6rem;
    }

    .chart-heading {
        margin-top: 1.5rem;
        margin-bottom: 0.35rem;
    }

    /* More breathing room around Streamlit's native blocks. */
    div[data-testid="stMetric"] {
        padding: 0.25rem 0.15rem 0.8rem 0.15rem;
    }

    div[data-testid="stExpander"] {
        margin-top: 0.55rem;
        margin-bottom: 0.85rem;
    }

    div[data-testid="stDataFrame"] {
        margin-top: 0.7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_streamlit_secrets() -> None:
    """Load optional Gemini configuration from Streamlit secrets."""
    try:
        for key in (
            "AI_PROVIDER",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "AI_TIMEOUT_SECONDS",
        ):
            if key not in os.environ and key in st.secrets:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass


def init_state() -> None:
    defaults = {
        "selected_case_id": None,
        "symptom_override": "",
        "topology_override": "",
        "evidence_override": "",
        "findings": None,
        "diagnosis": None,
        "diag_status": "",
        "review_action": None,
        "edited_diagnosis": None,
        "rejection_reason": "",
        "last_run_case_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_case_state() -> None:
    for key, value in {
        "symptom_override": "",
        "topology_override": "",
        "evidence_override": "",
        "findings": None,
        "diagnosis": None,
        "diag_status": "",
        "review_action": None,
        "edited_diagnosis": None,
        "rejection_reason": "",
        "last_run_case_id": None,
    }.items():
        st.session_state[key] = value


def severity_label(severity: str) -> str:
    value = (severity or "").strip().lower()
    return {
        "high": "🔴 High",
        "medium": "🟠 Medium",
        "low": "🟢 Low",
    }.get(value, severity or "—")


def review_metrics(records: list[dict]) -> tuple[int, int, int, int, float]:
    reviewed = len(records)
    approved = sum(r.get("human_action") == "approved" for r in records)
    edited = sum(r.get("human_action") == "edited" for r in records)
    rejected = sum(r.get("human_action") == "rejected" for r in records)
    accepted = approved + edited
    acceptance_rate = (accepted / reviewed * 100) if reviewed else 0.0
    return reviewed, approved, edited, rejected, acceptance_rate


def section(title: str, description: str) -> None:
    st.markdown(
        f'<h3 class="section-title">{title}</h3>'
        '<div class="section-rule"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="section-description">{description}</div>',
        unsafe_allow_html=True,
    )


def diagnosis_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="diagnosis-card">
            <div class="diagnosis-label">{label}</div>
            <div class="diagnosis-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Load configuration and state
# ---------------------------------------------------------------------------

load_streamlit_secrets()
init_state()


@st.cache_data(show_spinner=False)
def load_cases_cached():
    return load_cases(csv_path=DATA_PATH, strict_count=False)


try:
    all_cases = load_cases_cached()
    case_load_error = None
except CaseLoadError as exc:
    all_cases = []
    case_load_error = str(exc)

if case_load_error:
    st.error(f"Could not load the case dataset: {case_load_error}")
    st.stop()

if not all_cases:
    st.error("No cases are available in the dataset.")
    st.stop()

cases_by_id = {case.case_id: case for case in all_cases}
audit_records = read_records(limit=None)
reviewed, approved, edited, rejected, acceptance_rate = review_metrics(audit_records)

# Calculate verification coverage from the supplied 30-case dataset.
verified_cases = sum(
    bool(run_checker(case.symptom, case.topology_note, case.show_outputs))
    for case in all_cases
)
automated_rate = (
    verified_cases / len(all_cases) * 100
    if all_cases
    else 0.0
)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 🌐 NetSage AI")
    st.caption("Network Troubleshooting & Configuration Diagnostic Assistant")

    st.divider()
    st.markdown("### Scenario Selection")

    case_ids = [case.case_id for case in all_cases]
    default_index = (
        case_ids.index(st.session_state.selected_case_id)
        if st.session_state.selected_case_id in case_ids
        else 0
    )

    selected_case_id = st.selectbox(
        "Select Case ID",
        case_ids,
        index=default_index,
    )

    if selected_case_id != st.session_state.selected_case_id:
        st.session_state.selected_case_id = selected_case_id
        reset_case_state()

    with st.expander("Advanced Evidence Override"):
        st.caption(
            "Optional testing feature. These fields let you experiment with "
            "different evidence without changing the supplied case dataset."
        )
        st.session_state.symptom_override = st.text_area(
            "Symptom",
            value=st.session_state.symptom_override,
            height=80,
        )
        st.session_state.topology_override = st.text_area(
            "Topology Note",
            value=st.session_state.topology_override,
            height=80,
        )
        st.session_state.evidence_override = st.text_area(
            "Cisco Show Output",
            value=st.session_state.evidence_override,
            height=120,
        )

    st.divider()
    st.markdown("### Gemini Diagnosis")

    ai_client = AIClient()

    if ai_client.is_available():
        st.success(ai_client.status_message())
    else:
        st.warning(ai_client.status_message())

    st.caption(
        "Deterministic Rule Validation remains available when Gemini is not configured."
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="netsage-title">🌐 NetSage AI</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="netsage-subtitle">'
    "Network troubleshooting and configuration diagnostic assistant using "
    "deterministic verification, Gemini-assisted diagnosis, and human review."
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Dashboard summary — kept compact and separated from the main workflow.
# ---------------------------------------------------------------------------

st.markdown('<div class="metric-strip">', unsafe_allow_html=True)
k1, k2, k3 = st.columns(3, gap="large")
k1.metric("📚 Total Dataset Cases", len(all_cases))
k2.metric("🔍 Automated Verification Rate", f"{automated_rate:.0f}%")
k3.metric("🤝 Human Acceptance Rate", f"{acceptance_rate:.1f}%")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="small-note">'
    "Human acceptance includes approved and edited recommendations. "
    "Review decisions are retained in the audit log."
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Current case
# ---------------------------------------------------------------------------

current_case = cases_by_id.get(
    st.session_state.selected_case_id,
    all_cases[0],
)

effective_symptom = (
    st.session_state.symptom_override.strip()
    or current_case.symptom
)
effective_topology = (
    st.session_state.topology_override.strip()
    or current_case.topology_note
)
effective_evidence = (
    st.session_state.evidence_override.strip()
    or current_case.show_outputs
)


# ---------------------------------------------------------------------------
# 1. Scenario Inspection & Human Review Gate
# ---------------------------------------------------------------------------

section(
    "🔎 1. Scenario Inspection & Human Review Gate",
    "Review the selected case, network context, and captured Cisco show output "
    "before running verification.",
)

a, b, c, d = st.columns(4, gap="large")
a.metric("Case ID", current_case.case_id)
b.metric("OSI Layer", current_case.osi_layer or "—")
c.metric("Concept", current_case.concept_tag or "—")
d.metric("Severity", severity_label(current_case.severity))

st.markdown("**Symptom**")
st.info(effective_symptom)

st.markdown("**Topology Note**")
st.info(effective_topology)

st.markdown("**Expected Fault**")
st.success(current_case.expected_fault)

st.markdown("**Captured Cisco Show Output**")
st.code(effective_evidence, language="text")


# ---------------------------------------------------------------------------
# 2. Deterministic Rule Validation
# ---------------------------------------------------------------------------

section(
    "🧪 2. Deterministic Rule Validation",
    "The rule checker examines the symptom, topology note, and Cisco show output "
    "for known configuration and connectivity patterns.",
)

if st.button("🔍 Run Verification", use_container_width=False):
    with st.spinner("Running deterministic rule validation..."):
        st.session_state.findings = run_checker(
            effective_symptom,
            effective_topology,
            effective_evidence,
        )
        st.session_state.last_run_case_id = current_case.case_id

if (
    st.session_state.findings is None
    or st.session_state.last_run_case_id != current_case.case_id
):
    st.session_state.findings = run_checker(
        effective_symptom,
        effective_topology,
        effective_evidence,
    )
    st.session_state.last_run_case_id = current_case.case_id

findings = st.session_state.findings or []

if findings:
    st.success(f"{len(findings)} deterministic finding(s) matched.")
    with st.expander(f"Rule Checker Findings ({len(findings)})", expanded=True):
        for finding in findings:
            st.markdown(
                f"**{finding.title}** — {finding.severity} severity "
                f"(`{finding.rule_id}`)"
            )
            if finding.evidence:
                for evidence in finding.evidence:
                    st.caption(f"Evidence: {evidence}")
else:
    st.warning(
        "No deterministic rule matched this evidence. If Gemini is configured, "
        "the diagnosis step can still review the supplied case information."
    )


# ---------------------------------------------------------------------------
# 3. Diagnosis
# ---------------------------------------------------------------------------

section(
    "🧠 3. Diagnosis",
    "Generate a structured diagnosis from the deterministic findings and, "
    "when configured, Gemini's explanation.",
)

if st.button("✨ Generate Diagnosis", type="primary"):
    with st.spinner("Generating diagnosis..."):
        findings, diagnosis, status = diagnose(
            current_case.case_id,
            effective_symptom,
            effective_topology,
            effective_evidence,
            ai_client=ai_client,
        )
        st.session_state.findings = findings
        st.session_state.diagnosis = diagnosis
        st.session_state.diag_status = status
        st.session_state.review_action = None
        st.session_state.edited_diagnosis = None
        st.session_state.rejection_reason = ""

diagnosis: Diagnosis | None = st.session_state.diagnosis

if diagnosis is None:
    st.info(
        "Generate a diagnosis to view the root cause, evidence, next diagnostic "
        "command, and suggested fix."
    )
else:
    if diagnosis.source == "deterministic":
        st.warning(st.session_state.diag_status)
    else:
        st.success(st.session_state.diag_status)

    d1, d2, d3 = st.columns(3, gap="large")
    with d1:
        diagnosis_card("Root Cause", diagnosis.root_cause or "—")
    with d2:
        diagnosis_card("OSI Layer", diagnosis.osi_layer or "—")
    with d3:
        diagnosis_card("Confidence", f"{diagnosis.confidence:.0%}")

    st.markdown("#### Evidence")
    if diagnosis.evidence:
        for evidence in diagnosis.evidence:
            st.markdown(f"- {evidence}")
    else:
        st.caption("No evidence was returned.")

    st.markdown("#### Next Diagnostic Command")
    if diagnosis.next_command:
        st.code(diagnosis.next_command, language="text")
    else:
        st.caption("No command suggested.")

    st.markdown("#### Suggested Fix")
    if diagnosis.fix_steps:
        for index, step in enumerate(diagnosis.fix_steps, start=1):
            st.markdown(f"{index}. {step}")
    else:
        st.caption("No fix steps returned.")

    if diagnosis.explanation:
        with st.expander("Why this diagnosis?"):
            st.write(diagnosis.explanation)

    if diagnosis.caveats:
        st.info(f"**Caveat:** {diagnosis.caveats}")


# ---------------------------------------------------------------------------
# 4. Engineer Verification & Deployment Approval
# ---------------------------------------------------------------------------

section(
    "🛡️ 4. Engineer Verification & Deployment Approval",
    "An engineer reviews the recommendation before it is treated as actionable. "
    "NetSage does not execute Cisco configuration commands automatically.",
)

if diagnosis is None:
    st.caption("Generate a diagnosis before submitting a review decision.")
else:
    r1, r2, r3 = st.columns(3, gap="large")

    if r1.button("✅ Approve Recommendation", use_container_width=True):
        st.session_state.review_action = "approve"

    if r2.button("✏️ Edit Recommendation", use_container_width=True):
        st.session_state.review_action = "edit"

    if r3.button("❌ Reject Recommendation", use_container_width=True):
        st.session_state.review_action = "reject"

    action = st.session_state.review_action

    if action == "approve":
        st.success("The diagnosis will be logged as approved.")
        if st.button("Submit Approval"):
            append_record(
                current_case.case_id,
                effective_symptom,
                findings,
                diagnosis,
                "approved",
            )
            st.success(f"Audit decision logged for {current_case.case_id}.")
            st.session_state.review_action = None
            st.rerun()

    elif action == "edit":
        with st.form("edit_form"):
            e_root = st.text_area("Root Cause", value=diagnosis.root_cause)
            e_osi = st.text_input("OSI Layer", value=diagnosis.osi_layer)
            e_conf = st.slider(
                "Confidence",
                0.0,
                1.0,
                float(diagnosis.confidence),
            )
            e_command = st.text_input(
                "Next Diagnostic Command",
                value=diagnosis.next_command,
            )
            e_steps = st.text_area(
                "Suggested Fix — one step per line",
                value="\n".join(diagnosis.fix_steps),
            )
            submit_edit = st.form_submit_button("Submit Edited Diagnosis")

        if submit_edit:
            edited_diagnosis = Diagnosis(
                root_cause=e_root,
                osi_layer=e_osi,
                confidence=e_conf,
                evidence=diagnosis.evidence,
                next_command=e_command,
                fix_steps=[
                    step for step in e_steps.splitlines()
                    if step.strip()
                ],
                concept=diagnosis.concept,
                severity=diagnosis.severity,
                explanation=diagnosis.explanation,
                deterministic_findings=diagnosis.deterministic_findings,
                caveats=diagnosis.caveats,
                source="human-edited",
            )
            append_record(
                current_case.case_id,
                effective_symptom,
                findings,
                diagnosis,
                "edited",
                edited_diagnosis=edited_diagnosis,
            )
            st.session_state.edited_diagnosis = edited_diagnosis
            st.session_state.review_action = None
            st.success(f"Edited decision logged for {current_case.case_id}.")
            st.rerun()

    elif action == "reject":
        with st.form("reject_form"):
            reason = st.text_area("Rejection Reason")
            submit_reject = st.form_submit_button("Submit Rejection")

        if submit_reject:
            append_record(
                current_case.case_id,
                effective_symptom,
                findings,
                diagnosis,
                "rejected",
                rejection_reason=reason,
            )
            st.session_state.review_action = None
            st.success(f"Rejection logged for {current_case.case_id}.")
            st.rerun()


# ---------------------------------------------------------------------------
# 5. Dashboard & Statistics
# ---------------------------------------------------------------------------

section(
    "📊 5. Dashboard & Statistics",
    "A compact summary of the supplied troubleshooting cases and human review "
    "activity. Each chart is separated so the information remains easy to read.",
)

dash_records = read_records(limit=None)
reviewed, approved, edited, rejected, acceptance_rate = review_metrics(dash_records)

m1, m2, m3, m4, m5 = st.columns(5, gap="large")
m1.metric("Total Dataset Cases", len(all_cases))
m2.metric("Reviewed", reviewed)
m3.metric("Approved", approved)
m4.metric("Edited", edited)
m5.metric("Rejected", rejected)

st.markdown('<div class="chart-heading"><h4>🧩 Issue Types in Dataset</h4></div>',
            unsafe_allow_html=True)
issue_counts = (
    pd.Series([case.concept_tag for case in all_cases], name="Cases")
    .value_counts()
    .sort_values(ascending=True)
)
st.bar_chart(issue_counts, height=320)

st.markdown(
    '<div class="small-note">Number of supplied cases grouped by concept tag.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="chart-heading"><h4>⚠️ Severity Distribution</h4></div>',
            unsafe_allow_html=True)
severity_counts = (
    pd.Series([case.severity for case in all_cases], name="Cases")
    .value_counts()
    .reindex(["High", "Medium", "Low"])
    .fillna(0)
    .astype(int)
)
st.bar_chart(severity_counts, height=280)

st.markdown(
    '<div class="small-note">Severity levels represented in the supplied case dataset.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="chart-heading"><h4>🤝 Human Review Outcomes</h4></div>',
            unsafe_allow_html=True)
review_counts = pd.Series(
    [approved, edited, rejected],
    index=["Approved", "Edited", "Rejected"],
    name="Cases",
)
st.bar_chart(review_counts, height=280)

st.markdown(
    '<div class="small-note">Review decisions recorded through the human review gate.</div>',
    unsafe_allow_html=True,
)

with st.expander("Case Coverage Table"):
    coverage_rows = [
        {
            "Case ID": case.case_id,
            "Concept": case.concept_tag,
            "Severity": case.severity,
            "Expected Fault": case.expected_fault,
            "Rules Matched": len(
                run_checker(
                    case.symptom,
                    case.topology_note,
                    case.show_outputs,
                )
            ),
        }
        for case in all_cases
    ]
    st.dataframe(
        pd.DataFrame(coverage_rows),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# 6. Audit History
# ---------------------------------------------------------------------------

section(
    "📝 6. Audit History",
    "Every approval, edit, or rejection is retained for review and evaluation.",
)

if not dash_records:
    st.caption(
        "No audit records yet. Approve, edit, or reject a diagnosis to create one."
    )
else:
    for record in dash_records[:25]:
        action = record.get("human_action", "")
        icon = {
            "approved": "✅",
            "edited": "✏️",
            "rejected": "❌",
        }.get(action, "•")

        with st.expander(
            f"{icon} {record.get('timestamp', '')} — "
            f"{record.get('case_id', '')} — {action.upper()}"
        ):
            st.markdown(f"**Symptom:** {record.get('symptom', '')}")
            st.markdown(
                f"**Deterministic Findings:** "
                f"{record.get('deterministic_findings', '')}"
            )
            if record.get("confidence") is not None:
                st.markdown(
                    f"**Confidence:** {float(record['confidence']):.0%}"
                )
            if record.get("provider"):
                st.markdown(f"**Source:** {record.get('provider')}")
            if record.get("rejection_reason"):
                st.markdown(
                    f"**Rejection Reason:** {record.get('rejection_reason')}"
                )

st.divider()
st.caption(
    "NetSage AI is a decision-support tool. It recommends; an engineer reviews; "
    "every decision is logged. No Cisco configuration command is executed automatically."
)
