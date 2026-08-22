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
    """Bar chart: number of cases per concept_tag (issue type), sorted alphabetically."""
    counts = cases_df["concept_tag"].value_counts().reset_index()
    counts.columns = ["concept_tag", "count"]
    counts = counts.sort_values("concept_tag")
    fig = px.bar(
        counts, x="concept_tag", y="count",
        title="Cases by Concept Tag",
        labels={"concept_tag": "", "count": ""},
        color_discrete_sequence=["#2563eb"]
    )
    fig.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis_tickangle=-45,
        margin=dict(t=50, b=120, l=40, r=20),
        font=dict(family="Inter, sans-serif", size=12, color="#0f172a"),
        yaxis=dict(
            range=[0, 3.2],
            dtick=0.5,
            gridcolor="#e2e8f0",
            zerolinecolor="#e2e8f0"
        ),
        xaxis=dict(gridcolor="#e2e8f0")
    )
    fig.update_traces(marker_color="#2563eb")
    return fig


def cases_by_severity_chart(cases_df: pd.DataFrame):
    """Donut chart: number of cases per severity level."""
    counts = cases_df["severity"].value_counts().reset_index()
    counts.columns = ["severity", "count"]
    order = ["High", "Low", "Medium"]
    counts["severity"] = pd.Categorical(counts["severity"], categories=order, ordered=True)
    counts = counts.sort_values("severity").dropna()
    fig = px.pie(
        counts, names="severity", values="count",
        title="Cases by Severity",
        hole=0.55,
        color="severity",
        color_discrete_map={
            "High": "#ef4444",
            "Low": "#f59e0b",
            "Medium": "#22c55e",
        },
    )
    fig.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Inter, sans-serif", size=12, color="#0f172a"),
        margin=dict(t=50, b=40, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def review_status_chart(review_log_df: pd.DataFrame):
    """Donut chart: count of Accepted / Edited / Rejected human reviews."""
    if review_log_df.empty:
        return None
    counts = review_log_df["review_status"].value_counts().reset_index()
    counts.columns = ["review_status", "count"]
    order = ["Accepted", "Edited", "Rejected"]
    counts["review_status"] = pd.Categorical(counts["review_status"], categories=order, ordered=True)
    counts = counts.sort_values("review_status").dropna()
    fig = px.pie(
        counts, names="review_status", values="count",
        title="Review Outcome Breakdown",
        hole=0.55,
        color="review_status",
        color_discrete_map={"Accepted": "#22c55e", "Edited": "#f59e0b", "Rejected": "#ef4444"},
    )
    fig.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Inter, sans-serif", size=12, color="#0f172a"),
        margin=dict(t=50, b=40, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def agreement_rate_chart(review_log_df: pd.DataFrame):
    """Donut chart: AI-vs-human agreement rate based on review log status / comparison."""
    if review_log_df.empty:
        return None
    
    accepted = (review_log_df["review_status"] == "Accepted").sum()
    others = len(review_log_df) - accepted
    df_agreed = pd.DataFrame([
        {"Status": "Agreed (Accepted)", "count": accepted},
        {"Status": "Disagreed (Edited/Rejected)", "count": others}
    ])
    fig = px.pie(
        df_agreed, names="Status", values="count",
        title="AI vs Human Agreement Rate",
        hole=0.55,
        color="Status",
        color_discrete_map={"Agreed (Accepted)": "#22c55e", "Disagreed (Edited/Rejected)": "#ef4444"},
    )
    fig.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Inter, sans-serif", size=12, color="#0f172a"),
        margin=dict(t=50, b=40, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def compute_agreement_percentage(review_log_df: pd.DataFrame) -> float:
    """Returns the percentage (0-100) of logged reviews where the AI got an Accepted / Match decision."""
    if review_log_df.empty:
        return 0.0
    total = len(review_log_df)
    accepted = (review_log_df["review_status"] == "Accepted").sum()
    return round((accepted / total) * 100, 1) if total else 0.0
