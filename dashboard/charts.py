"""
dashboard/charts.py
---------------------
Chart-building functions for the Streamlit dashboard tab.
Each function takes a pandas DataFrame and returns a Plotly figure.
Keeping these separate from app.py keeps the Streamlit file focused on
layout/UI, and makes each chart independently testable.
"""

import pandas as pd
import plotly.express as px


def cases_by_concept_tag_chart(cases_df: pd.DataFrame):
    """Bar chart: number of cases per concept_tag (issue type)."""
    counts = cases_df["concept_tag"].value_counts().reset_index()
    counts.columns = ["concept_tag", "count"]
    fig = px.bar(
        counts, x="concept_tag", y="count",
        title="Cases by Issue Type / Concept Tag",
        labels={"concept_tag": "Concept Tag", "count": "Number of Cases"},
    )
    fig.update_layout(xaxis_tickangle=-40, margin=dict(t=50, b=120))
    return fig


def cases_by_severity_chart(cases_df: pd.DataFrame):
    """Pie chart: number of cases per severity level."""
    counts = cases_df["severity"].value_counts().reset_index()
    counts.columns = ["severity", "count"]
    # Keep a sensible severity order when present
    order = ["Critical", "High", "Medium", "Low"]
    counts["severity"] = pd.Categorical(counts["severity"], categories=order, ordered=True)
    counts = counts.sort_values("severity")
    fig = px.pie(
        counts, names="severity", values="count",
        title="Cases by Severity",
        color="severity",
        color_discrete_map={
            "Critical": "#b30000", "High": "#e6550d",
            "Medium": "#fdae6b", "Low": "#31a354",
        },
    )
    return fig


def review_status_chart(review_log_df: pd.DataFrame):
    """Bar chart: count of Accepted / Edited / Rejected human reviews."""
    if review_log_df.empty:
        return None
    counts = review_log_df["review_status"].value_counts().reset_index()
    counts.columns = ["review_status", "count"]
    fig = px.bar(
        counts, x="review_status", y="count",
        title="Human Review Outcomes",
        labels={"review_status": "Review Status", "count": "Number of Reviews"},
        color="review_status",
        color_discrete_map={"Accepted": "#31a354", "Edited": "#fdae6b", "Rejected": "#e34a33"},
    )
    return fig


def agreement_rate_chart(review_log_df: pd.DataFrame):
    """Pie chart: AI-vs-human agreement rate based on the comparison_result column."""
    if review_log_df.empty or "comparison_result" not in review_log_df.columns:
        return None
    counts = review_log_df["comparison_result"].value_counts().reset_index()
    counts.columns = ["comparison_result", "count"]
    fig = px.pie(
        counts, names="comparison_result", values="count",
        title="AI vs Expected Fault Agreement",
        color="comparison_result",
        color_discrete_map={"Match": "#31a354", "Partial Match": "#fdae6b", "No Match": "#e34a33"},
    )
    return fig


def compute_agreement_percentage(review_log_df: pd.DataFrame) -> float:
    """Returns the percentage (0-100) of logged reviews where the AI got a full 'Match'."""
    if review_log_df.empty or "comparison_result" not in review_log_df.columns:
        return 0.0
    total = len(review_log_df)
    matches = (review_log_df["comparison_result"] == "Match").sum()
    return round((matches / total) * 100, 1) if total else 0.0
