"""
app.py
-------
NetSage AI - AI-Assisted Cisco Network Troubleshooting System
A simple Streamlit dashboard built for a Cisco internship submission.

This is a BEGINNER-FRIENDLY, single-file Streamlit app with heavy
comments explaining what each section does. It ties together:
    1. Case Explorer       - browse the 30 sample troubleshooting cases
    2. AI Diagnosis        - run a mock AI diagnosis on the selected case
    3. Rule Checker         - run deterministic Python checks (no AI)
    4. AI Comparison        - compare the AI's answer to the known fault
    5. Human Review          - log a human's Accept/Edit/Reject decision
    6. Dashboard              - charts summarizing all of the above

Run with:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
import csv
from datetime import datetime

import pandas as pd
import streamlit as st

# Local modules (see their own files for detailed comments)
from ai.diagnosis import get_ai_diagnosis
from ai.compare_answers import get_comparison_details
from checker.rule_checker import run_all_checks
from dashboard.charts import (
    cases_by_concept_tag_chart,
    cases_by_severity_chart,
    review_status_chart,
    agreement_rate_chart,
    compute_agreement_percentage,
)

# ---------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
CASES_CSV = os.path.join(HERE, "data", "cases.csv")
LOG_CSV = os.path.join(HERE, "logs", "responsible_ai_log.csv")
LOG_DIR = os.path.dirname(LOG_CSV)

LOG_FIELDNAMES = [
    "timestamp", "case_id", "ai_root_cause", "ai_confidence",
    "expected_fault", "comparison_result", "review_status",
    "corrected_answer", "reviewer_notes",
]


# ---------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------
@st.cache_data
def load_cases() -> pd.DataFrame:
    """Load the 30 sample troubleshooting cases from CSV."""
    return pd.read_csv(CASES_CSV, dtype=str)


def load_review_log() -> pd.DataFrame:
    """Load the responsible AI review log from CSV sorted by timestamp (most recent first)."""
    if not os.path.exists(LOG_CSV) or os.path.getsize(LOG_CSV) == 0:
        return pd.DataFrame(columns=LOG_FIELDNAMES)
    try:
        df = pd.read_csv(LOG_CSV, dtype=str).fillna("")
    except pd.errors.ParserError:
        # If the CSV file is malformed, try a more forgiving fallback.
        with open(LOG_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader]
        df = pd.DataFrame(rows, columns=LOG_FIELDNAMES).fillna("")

    if "timestamp" in df.columns and not df.empty:
        df = df.sort_values(by="timestamp", ascending=False)
    return df



def append_review_log(row: dict):
    """Append a single review record to logs/responsible_ai_log.csv."""
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.exists(LOG_CSV) and os.path.getsize(LOG_CSV) > 0
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------
st.set_page_config(page_title="NetSage AI", page_icon="🛰️", layout="wide")

st.title("🛰️ NetSage AI")
st.caption("AI-Assisted Cisco Network Troubleshooting System — student demo project")

cases_df = load_cases()

# Keep the currently selected case and its AI diagnosis in session_state
# so it persists as the user clicks buttons and switches tabs.
if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = cases_df.iloc[0]["case_id"]
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None
if "checker_results" not in st.session_state:
    st.session_state.checker_results = None
if "comparison_result" not in st.session_state:
    st.session_state.comparison_result = None

tabs = st.tabs([
    "1. Case Explorer",
    "2. AI Diagnosis",
    "3. Rule Checker",
    "4. AI Comparison",
    "5. Human Review",
    "6. Dashboard",
])

# =======================================================================
# TAB 1 - CASE EXPLORER
# =======================================================================
with tabs[0]:
    st.header("Case Explorer")
    st.write("Select a troubleshooting case to review its evidence.")

    # Dropdown showing "C001 - Duplicate IP" style labels for readability
    case_labels = [
        f"{row.case_id} — {row.concept_tag} ({row.severity})"
        for row in cases_df.itertuples()
    ]
    label_to_id = dict(zip(case_labels, cases_df["case_id"]))

    default_index = list(cases_df["case_id"]).index(st.session_state.selected_case_id)
    selected_label = st.selectbox("Choose a case:", case_labels, index=default_index)
    new_case_id = label_to_id[selected_label]
    if new_case_id != st.session_state.selected_case_id:
        st.session_state.selected_case_id = new_case_id
        st.session_state.ai_result = None
        st.session_state.checker_results = None
        st.session_state.comparison_result = None

    case = cases_df[cases_df["case_id"] == st.session_state.selected_case_id].iloc[0]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Symptom")
        st.info(case["symptom"])
        st.subheader("Topology Note")
        st.write(case["topology_note"])
        st.subheader("Show Output")
        st.code(case["show_outputs"], language="text")

    with col2:
        st.subheader("Case Metadata")
        st.markdown(f"**OSI Layer:** {case['osi_layer']}")
        st.markdown(f"**Concept Tag:** {case['concept_tag']}")
        st.markdown(f"**Severity:** {case['severity']}")
        st.subheader("Expected Fault (known answer)")
        st.success(case["expected_fault"])
        st.caption(
            "The expected fault is the known-correct answer used for grading "
            "the AI's diagnosis. In a real NOC this would not be shown to the "
            "AI, only used afterward for comparison."
        )

# =======================================================================
# TAB 2 - AI DIAGNOSIS
# =======================================================================
with tabs[1]:
    st.header("AI Diagnosis")
    st.write(f"Selected case: **{st.session_state.selected_case_id}**")
    st.caption(
        "This uses a mock AI function (ai/diagnosis.py) that returns realistic, "
        "structured JSON — no API key required. See prompts/diagnose_prompt.md "
        "for the prompt design this mock is standing in for."
    )

    if st.button("🤖 Run AI Diagnosis"):
        case = cases_df[cases_df["case_id"] == st.session_state.selected_case_id].iloc[0].to_dict()
        st.session_state.ai_result = get_ai_diagnosis(case)
        # Reset downstream results since the diagnosis changed
        st.session_state.comparison_result = None

    if st.session_state.ai_result:
        result = st.session_state.ai_result
        st.markdown("### Structured AI Output")
        st.markdown(f"**Root Cause:** {result['root_cause']}")

        confidence = result["confidence"]
        if isinstance(confidence, (int, float)):
            confidence_label = f"{confidence:.0%}" if 0 <= confidence <= 1 else str(confidence)
            confidence_color = "green" if confidence >= 0.85 else "orange" if confidence >= 0.5 else "red"
        else:
            confidence_label = confidence
            confidence_color = {"High": "green", "Medium": "orange", "Low": "red"}.get(confidence, "gray")

        st.markdown(f"**Confidence:** :{confidence_color}[{confidence_label}]")

        evidence = result["evidence"]
        if isinstance(evidence, list):
            st.markdown("**Evidence:**")
            for item in evidence:
                st.markdown(f"- {item}")
        else:
            st.markdown(f"**Evidence:** {evidence}")

        st.markdown(f"**Suggested Next Command:** `{result['next_command']}`")

        st.markdown("**Fix Steps:**")
        for i, step in enumerate(result["fix_steps"], start=1):
            st.markdown(f"{i}. {step}")

        st.warning(
            "⚠️ This AI diagnosis is a draft and REQUIRES HUMAN REVIEW before "
            "being applied to production network equipment. Go to the "
            "**Human Review** tab to accept, edit, or reject this answer."
        )
    else:
        st.info("Click 'Run AI Diagnosis' to generate a structured diagnosis for this case.")

# =======================================================================
# TAB 3 - RULE CHECKER
# =======================================================================
with tabs[2]:
    st.header("Rule Checker (Deterministic, Non-AI)")
    st.write(f"Selected case: **{st.session_state.selected_case_id}**")
    st.caption(
        "This runs plain Python logic (checker/rule_checker.py) against the "
        "case's show output — no AI involved. It checks for duplicate IPs, "
        "wrong subnet masks, gateway mismatches, interface-down states, "
        "missing VLANs, and missing routes."
    )

    if st.button("🔍 Run Rule Checker"):
        case = cases_df[cases_df["case_id"] == st.session_state.selected_case_id].iloc[0].to_dict()
        st.session_state.checker_results = run_all_checks(case)

    if st.session_state.checker_results:
        for result in st.session_state.checker_results:
            if result["result"] == "FAIL":
                st.error(f"❌ **{result['check']}** — {result['detail']}")
            else:
                st.success(f"✅ **{result['check']}** — {result['detail']}")
    else:
        st.info("Click 'Run Rule Checker' to evaluate this case with deterministic checks.")

# =======================================================================
# TAB 4 - AI COMPARISON
# =======================================================================
with tabs[3]:
    st.header("AI Comparison")
    st.write(f"Selected case: **{st.session_state.selected_case_id}**")
    st.caption(
        "Compares the AI diagnosis's root cause with the case's known "
        "expected_fault, and classifies the result as Match, Partial Match, "
        "or No Match, based on shared technical keywords."
    )

    case = cases_df[cases_df["case_id"] == st.session_state.selected_case_id].iloc[0]

    if st.session_state.ai_result is None:
        st.info("Run the AI Diagnosis (Tab 2) first, then come back here to compare it.")
    else:
        if st.button("⚖️ Compare AI Diagnosis to Expected Fault"):
            details = get_comparison_details(
                st.session_state.ai_result["root_cause"], case["expected_fault"]
            )
            st.session_state.comparison_result = details

        if st.session_state.comparison_result:
            details = st.session_state.comparison_result
            result_icon = {"Match": "✅", "Partial Match": "🟡", "No Match": "❌"}
            st.markdown(f"### {result_icon.get(details['result'], '')} {details['result']}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**AI Root Cause:**")
                st.write(st.session_state.ai_result["root_cause"])
            with col2:
                st.markdown("**Expected Fault (known answer):**")
                st.write(case["expected_fault"])

            if details["overlapping_keywords"]:
                st.markdown("**Overlapping keywords:** " + ", ".join(details["overlapping_keywords"]))

# =======================================================================
# TAB 5 - HUMAN REVIEW
# =======================================================================
with tabs[4]:
    st.header("Human Review")
    st.write(f"Selected case: **{st.session_state.selected_case_id}**")
    st.caption(
        "A human reviewer must Accept, Edit, or Reject every AI diagnosis "
        "before it is treated as final. All decisions are logged to "
        "logs/responsible_ai_log.csv for auditability."
    )

    if st.session_state.ai_result is None:
        st.info("Run the AI Diagnosis (Tab 2) first — there's nothing to review yet.")
    else:
        case = cases_df[cases_df["case_id"] == st.session_state.selected_case_id].iloc[0]
        ai_result = st.session_state.ai_result

        st.markdown("**AI Root Cause being reviewed:**")
        st.write(ai_result["root_cause"])

        review_status = st.radio(
            "Reviewer decision:",
            ["Accepted", "Edited", "Rejected"],
            horizontal=True,
        )

        corrected_answer = ""
        reviewer_notes = st.text_area("Reviewer notes (optional but recommended):", height=80)

        if review_status in ("Edited", "Rejected"):
            corrected_answer = st.text_area(
                "Corrected answer (required for Edited/Rejected):", height=100
            )

        if st.button("💾 Save Review to Log"):
            if review_status in ("Edited", "Rejected") and not corrected_answer.strip():
                st.error("Please provide a corrected answer for an Edited or Rejected review.")
            else:
                # Compute (or reuse) the comparison result for the log entry
                if st.session_state.comparison_result:
                    comparison_result = st.session_state.comparison_result["result"]
                else:
                    comparison_result = get_comparison_details(
                        ai_result["root_cause"], case["expected_fault"]
                    )["result"]

                log_row = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "case_id": case["case_id"],
                    "ai_root_cause": ai_result["root_cause"],
                    "ai_confidence": ai_result["confidence"],
                    "expected_fault": case["expected_fault"],
                    "comparison_result": comparison_result,
                    "review_status": review_status,
                    "corrected_answer": corrected_answer,
                    "reviewer_notes": reviewer_notes,
                }
                append_review_log(log_row)
                st.success(f"Review saved for case {case['case_id']} — status: {review_status}")

    st.divider()
    st.subheader("Review Log (most recent first)")
    log_df = load_review_log()
    if log_df.empty:
        st.info("No reviews logged yet.")
    else:
        st.dataframe(log_df, use_container_width=True, hide_index=True)


# =======================================================================
# TAB 6 - DASHBOARD
# =======================================================================
with tabs[5]:
    st.header("Dashboard")
    log_df = load_review_log()

    # --- Top metrics row ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Cases", len(cases_df))
    m2.metric("Total Reviews Logged", len(log_df))
    agreement_pct = compute_agreement_percentage(log_df)
    m3.metric("AI-vs-Human Agreement", f"{agreement_pct}%")
    accepted_count = (log_df["review_status"] == "Accepted").sum() if not log_df.empty else 0
    m4.metric("Accepted Reviews", int(accepted_count))

    st.divider()

    # --- Case-level charts (always available, based on data/cases.csv) ---
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(cases_by_concept_tag_chart(cases_df), use_container_width=True)
    with col2:
        st.plotly_chart(cases_by_severity_chart(cases_df), use_container_width=True)

    st.divider()

    # --- Review-log-level charts (depend on logs/responsible_ai_log.csv) ---
    if log_df.empty:
        st.info("No review log data yet — run some diagnoses and submit reviews to populate these charts.")
    else:
        col3, col4 = st.columns(2)
        with col3:
            fig = review_status_chart(log_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col4:
            fig = agreement_rate_chart(log_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        st.subheader("Review Totals")
        status_counts = log_df["review_status"].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("Accepted", int(status_counts.get("Accepted", 0)))
        c2.metric("Edited", int(status_counts.get("Edited", 0)))
        c3.metric("Rejected", int(status_counts.get("Rejected", 0)))
