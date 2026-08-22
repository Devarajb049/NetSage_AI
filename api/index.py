import os
import sys
import csv
import json
from datetime import datetime
import pandas as pd
from flask import Flask, jsonify, request, render_template_string, send_from_directory

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Import existing domain logic
from ai.diagnosis import get_ai_diagnosis
from ai.compare_answers import get_comparison_details
from checker.rule_checker import run_all_checks

app = Flask(__name__)

CASES_CSV = os.path.join(HERE, "data", "cases.csv")
LOG_CSV = os.path.join(HERE, "logs", "responsible_ai_log.csv")
LOG_DIR = os.path.dirname(LOG_CSV)

LOG_FIELDNAMES = [
    "timestamp", "case_id", "ai_root_cause", "ai_confidence",
    "expected_fault", "comparison_result", "review_status",
    "corrected_answer", "reviewer_notes"
]

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    assets_dir = os.path.join(HERE, "assets")
    return send_from_directory(assets_dir, filename)

def load_cases_df():
    if os.path.exists(CASES_CSV):
        return pd.read_csv(CASES_CSV, dtype=str).fillna("")
    return pd.DataFrame()

def load_review_log_df():
    if not os.path.exists(LOG_CSV) or os.path.getsize(LOG_CSV) == 0:
        return pd.DataFrame(columns=LOG_FIELDNAMES)
    try:
        df = pd.read_csv(LOG_CSV, dtype=str).fillna("")
    except Exception:
        with open(LOG_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader]
        df = pd.DataFrame(rows, columns=LOG_FIELDNAMES).fillna("")

    if "timestamp" in df.columns and not df.empty:
        df = df.sort_values(by="timestamp", ascending=False)
    return df

def append_review_log(row_dict):
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.exists(LOG_CSV) and os.path.getsize(LOG_CSV) > 0
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)

@app.route("/api/cases", methods=["GET"])
def get_cases():
    df = load_cases_df()
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    data = request.json or {}
    case_id = data.get("case_id")
    df = load_cases_df()
    match = df[df["case_id"] == case_id]
    if match.empty:
        return jsonify({"error": f"Case {case_id} not found"}), 404
    case = match.iloc[0].to_dict()
    diagnosis = get_ai_diagnosis(case)
    return jsonify(diagnosis)

@app.route("/api/checker", methods=["POST"])
def api_checker():
    data = request.json or {}
    case_id = data.get("case_id")
    df = load_cases_df()
    match = df[df["case_id"] == case_id]
    if match.empty:
        return jsonify({"error": f"Case {case_id} not found"}), 404
    case = match.iloc[0].to_dict()
    checks = run_all_checks(case)
    return jsonify(checks)

@app.route("/api/compare", methods=["POST"])
def api_compare():
    data = request.json or {}
    ai_root_cause = data.get("ai_root_cause", "")
    expected_fault = data.get("expected_fault", "")
    res = get_comparison_details(ai_root_cause, expected_fault)
    return jsonify(res)

@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    df = load_review_log_df()
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/review", methods=["POST"])
def api_review():
    data = request.json or {}
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "case_id": data.get("case_id", ""),
        "ai_root_cause": data.get("ai_root_cause", ""),
        "ai_confidence": data.get("ai_confidence", ""),
        "expected_fault": data.get("expected_fault", ""),
        "comparison_result": data.get("comparison_result", ""),
        "review_status": data.get("review_status", ""),
        "corrected_answer": data.get("corrected_answer", ""),
        "reviewer_notes": data.get("reviewer_notes", ""),
    }
    append_review_log(row)
    return jsonify({"status": "success", "record": row})

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    cases_df = load_cases_df()
    reviews_df = load_review_log_df()

    # Cases by Concept/Tag (alphabetically sorted)
    concept_counts = {}
    if "concept_tag" in cases_df.columns:
        s_concept = cases_df["concept_tag"].value_counts().sort_index()
        concept_counts = s_concept.to_dict()

    # Cases by Severity (High, Low, Medium order)
    severity_counts = {}
    if "severity" in cases_df.columns:
        s_sev = cases_df["severity"].value_counts()
        for sev in ["High", "Low", "Medium"]:
            if sev in s_sev:
                severity_counts[sev] = int(s_sev[sev])

    # Review status
    review_status_counts = {}
    if "review_status" in reviews_df.columns and not reviews_df.empty:
        review_status_counts = reviews_df["review_status"].value_counts().to_dict()

    # Agreement rate
    total_reviews = len(reviews_df)
    accepted_reviews = int((reviews_df["review_status"] == "Accepted").sum()) if total_reviews > 0 else 0
    edited_reviews = int((reviews_df["review_status"] == "Edited").sum()) if total_reviews > 0 else 0
    rejected_reviews = int((reviews_df["review_status"] == "Rejected").sum()) if total_reviews > 0 else 0
    agreement_rate = round((accepted_reviews / total_reviews * 100), 1) if total_reviews > 0 else 0.0

    return jsonify({
        "total_cases": len(cases_df),
        "total_reviews": total_reviews,
        "agreement_rate": agreement_rate,
        "accepted_reviews": accepted_reviews,
        "edited_reviews": edited_reviews,
        "rejected_reviews": rejected_reviews,
        "concept_counts": concept_counts,
        "severity_counts": severity_counts,
        "review_status_counts": review_status_counts
    })


PERFECT_RESPONSIVE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NetSage AI</title>
  <link rel="icon" type="image/png" href="/assets/logo.png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    :root {
      --bg-main: #f8fafc;
      --card-bg: #ffffff;
      --card-border: #e2e8f0;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --primary-accent: #2563eb;
      --primary-hover: #1d4ed8;
      --blue-bg: #eff6ff;
      --blue-border: #3b82f6;
      --blue-text: #1e40af;
      --green-bg: #f0fdf4;
      --green-border: #22c55e;
      --green-text: #166534;
      --amber-bg: #fffbeb;
      --amber-border: #f59e0b;
      --amber-text: #92400e;
      --red-bg: #fef2f2;
      --red-border: #ef4444;
      --red-text: #991b1b;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg-main);
      color: var(--text-main);
      min-height: 100vh;
      font-size: 0.88rem;
    }

    /* Outer Wrapper Layout */
    .app-layout {
      display: flex;
      min-height: 100vh;
      width: 100%;
      position: relative;
    }

    /* Top Mobile Bar (Hidden on Desktop) */
    .mobile-topbar {
      display: none;
      width: 100%;
      background: #ffffff;
      border-bottom: 1px solid var(--card-border);
      padding: 0.75rem 1.25rem;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 90;
    }
    .mobile-topbar-brand {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      font-weight: 700;
      font-size: 1.1rem;
      color: var(--text-main);
    }
    .mobile-topbar-logo { width: 34px; height: 34px; border-radius: 6px; object-fit: contain; }
    .mobile-menu-btn {
      background: #f1f5f9;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 0.4rem 0.6rem;
      cursor: pointer;
      color: var(--text-main);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* Left Sidebar Navigation */
    .sidebar {
      width: 270px;
      background: #ffffff;
      border-right: 1px solid var(--card-border);
      position: fixed;
      top: 0;
      bottom: 0;
      left: 0;
      display: flex;
      flex-direction: column;
      padding: 1.25rem 0.85rem;
      z-index: 100;
      transition: width 0.25s ease-in-out, transform 0.25s ease-in-out;
      box-shadow: 2px 0 8px rgba(0, 0, 0, 0.02);
      overflow-x: hidden;
    }

    .sidebar-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.4);
      z-index: 95;
      backdrop-filter: blur(2px);
    }

    .sidebar-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      padding-bottom: 1rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid var(--card-border);
    }
    .sidebar-brand-wrapper {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      overflow: hidden;
    }
    .sidebar-logo {
      width: 44px;
      height: 44px;
      border-radius: 8px;
      object-fit: contain;
      flex-shrink: 0;
    }
    .sidebar-title-group {
      white-space: nowrap;
    }
    .sidebar-title-group h1 {
      font-size: 1.2rem;
      font-weight: 700;
      color: var(--text-main);
      margin: 0;
      line-height: 1.2;
    }
    .sidebar-caption {
      color: var(--text-muted);
      font-size: 0.75rem;
    }

    .sidebar-toggle-btn {
      background: transparent;
      border: none;
      padding: 0.35rem;
      cursor: pointer;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 6px;
      transition: all 0.2s ease;
      flex-shrink: 0;
    }
    .sidebar-toggle-btn:hover {
      color: var(--primary-accent);
      background: #f1f5f9;
    }

    /* Vertical Navigation Items */
    .sidebar-nav {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      flex: 1;
    }
    .st-tab {
      padding: 0.75rem 0.9rem;
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--text-muted);
      cursor: pointer;
      border-radius: 8px;
      border-left: 3px solid transparent;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 0.65rem;
      white-space: nowrap;
    }
    .st-tab:hover {
      background: #f8fafc;
      color: var(--text-main);
    }
    .st-tab.active {
      color: var(--primary-accent);
      background: var(--blue-bg);
      border-left-color: var(--primary-accent);
    }
    .st-tab i { width: 18px; height: 18px; flex-shrink: 0; }

    .sidebar-footer {
      padding-top: 1rem;
      border-top: 1px solid var(--card-border);
      font-size: 0.78rem;
      color: var(--text-muted);
      white-space: nowrap;
    }

    /* COLLAPSED SIDEBAR STATE (DESKTOP) */
    .sidebar.collapsed {
      width: 72px;
      padding: 1.25rem 0.5rem;
    }
    .sidebar.collapsed .sidebar-title-group,
    .sidebar.collapsed .tab-label-text,
    .sidebar.collapsed .sidebar-footer-text {
      display: none !important;
    }
    .sidebar.collapsed .sidebar-header {
      flex-direction: column;
      align-items: center;
      gap: 0.65rem;
      padding-bottom: 0.75rem;
    }
    .sidebar.collapsed .sidebar-brand-wrapper {
      justify-content: center;
      width: 100%;
    }
    .sidebar.collapsed .sidebar-logo {
      width: 38px;
      height: 38px;
      display: block !important;
      margin: 0 auto;
    }
    .sidebar.collapsed .sidebar-toggle-btn {
      width: 32px;
      height: 32px;
      padding: 0;
    }
    .sidebar.collapsed .st-tab {
      justify-content: center;
      padding: 0.75rem 0;
    }
    .sidebar.collapsed .st-tab i {
      margin: 0;
      width: 20px;
      height: 20px;
    }

    /* Main Content Area */
    .main-content {
      margin-left: 270px;
      flex: 1;
      padding: 2rem 3.5rem;
      min-width: 0;
      transition: margin-left 0.25s ease-in-out;
    }
    .sidebar.collapsed + .main-content {
      margin-left: 72px;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    /* Layout & Columns */
    .st-row { display: flex; gap: 1.25rem; margin-bottom: 1.25rem; }
    .st-col { flex: 1; min-width: 0; }

    /* Cards */
    .st-card {
      background: var(--card-bg);
      border-radius: 10px;
      padding: 1.25rem;
      border: 1px solid var(--card-border);
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      margin-bottom: 1.25rem;
    }

    /* Inputs */
    label {
      display: block;
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--text-main);
      margin-bottom: 0.3rem;
    }
    select, input[type="text"], textarea {
      width: 100%;
      padding: 0.5rem 0.75rem;
      background: #ffffff;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 0.88rem;
      margin-bottom: 0.85rem;
      transition: border-color 0.2s ease;
    }
    select:focus, input:focus, textarea:focus {
      outline: none;
      border-color: var(--primary-accent);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }

    /* Buttons */
    .st-btn {
      background: var(--primary-accent);
      color: #ffffff;
      border: none;
      padding: 0.5rem 1rem;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      margin-bottom: 1rem;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .st-btn:hover {
      background: var(--primary-hover);
    }
    .st-btn i { width: 16px; height: 16px; }

    /* Alerts */
    .st-alert {
      padding: 0.75rem 0.9rem;
      border-radius: 6px;
      font-size: 0.88rem;
      margin-bottom: 0.85rem;
      line-height: 1.45;
      display: flex;
      align-items: flex-start;
      gap: 0.6rem;
    }
    .st-alert i { width: 18px; height: 18px; flex-shrink: 0; margin-top: 2px; }
    .st-info { background: var(--blue-bg); border-left: 4px solid var(--blue-border); color: var(--blue-text); }
    .st-success { background: var(--green-bg); border-left: 4px solid var(--green-border); color: var(--green-text); }
    .st-warning { background: var(--amber-bg); border-left: 4px solid var(--amber-border); color: var(--amber-text); }
    .st-error { background: var(--red-bg); border-left: 4px solid var(--red-border); color: var(--red-text); }

    /* Code Box */
    .st-code {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 0.75rem 0.9rem;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 0.82rem;
      color: #f8fafc;
      white-space: pre-wrap;
      word-break: break-all;
      margin-bottom: 0.85rem;
    }

    /* Metric Cards */
    .st-metric-card {
      background: #ffffff;
      border-radius: 8px;
      padding: 1rem;
      border: 1px solid var(--card-border);
      text-align: left;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .st-metric-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .st-metric-val { font-size: 1.5rem; font-weight: 700; color: var(--text-main); margin-top: 0.2rem; }

    /* Radio Buttons */
    .radio-group { display: flex; gap: 1.25rem; margin-bottom: 0.85rem; }
    .radio-label { display: flex; align-items: center; gap: 0.35rem; cursor: pointer; font-size: 0.88rem; font-weight: 500; }

    /* Data Table */
    .st-table-container {
      background: #ffffff;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      overflow-x: auto;
      margin-top: 0.85rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th { background: #f1f5f9; color: var(--text-muted); padding: 0.6rem 0.8rem; text-align: left; font-weight: 600; border-bottom: 1px solid var(--card-border); }
    td { padding: 0.6rem 0.8rem; border-bottom: 1px solid #f1f5f9; color: var(--text-main); vertical-align: top; }
    tr:hover { background: #f8fafc; }

    h2 { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.4rem; color: var(--text-main); }
    h3 { font-size: 1.05rem; font-weight: 600; margin-top: 0.85rem; margin-bottom: 0.4rem; color: var(--text-main); }
    hr { border: none; height: 1px; background: var(--card-border); margin: 1.5rem 0; }

    /* RESPONSIVE MEDIA QUERIES */
    @media (max-width: 1024px) {
      .mobile-topbar { display: flex; }
      .sidebar-toggle-btn { display: none !important; }
      .sidebar {
        width: 270px !important;
        transform: translateX(-100%);
        box-shadow: 4px 0 16px rgba(0,0,0,0.1);
      }
      .sidebar.open {
        transform: translateX(0) !important;
      }
      .sidebar.collapsed {
        width: 270px !important;
        padding: 1.25rem 0.85rem !important;
      }
      .sidebar.collapsed .sidebar-title-group,
      .sidebar.collapsed .tab-label-text,
      .sidebar.collapsed .sidebar-footer-text {
        display: block !important;
      }
      .sidebar.collapsed .sidebar-header {
        flex-direction: row !important;
        justify-content: space-between !important;
      }
      .sidebar.collapsed .sidebar-brand-wrapper {
        justify-content: flex-start !important;
        width: auto !important;
      }
      .sidebar.collapsed .sidebar-logo {
        width: 44px !important;
        height: 44px !important;
        margin: 0 !important;
      }
      .sidebar.collapsed .st-tab {
        justify-content: flex-start !important;
        padding: 0.75rem 0.9rem !important;
      }
      .sidebar-overlay.open {
        display: block;
      }
      .main-content {
        margin-left: 0 !important;
        padding: 1.25rem 1rem;
      }
      .st-row {
        flex-wrap: wrap;
      }
      .st-col {
        flex: 1 1 calc(50% - 0.75rem);
        min-width: 260px;
      }
    }

    @media (max-width: 768px) {
      .main-content {
        padding: 1rem 0.75rem;
      }
      .st-row {
        flex-direction: column;
        gap: 1rem;
      }
      .st-col {
        flex: 1 1 100%;
        width: 100%;
      }
      .radio-group {
        flex-direction: column;
        gap: 0.6rem;
      }
      .st-metric-val {
        font-size: 1.35rem;
      }
      th, td {
        padding: 0.5rem 0.65rem;
      }
    }
  </style>
</head>
<body>

  <!-- Mobile Top Navigation Header -->
  <div class="mobile-topbar">
    <div class="mobile-topbar-brand">
      <img src="/assets/logo.png" alt="NetSage AI" class="mobile-topbar-logo">
      <span>NetSage AI</span>
    </div>
    <button class="mobile-menu-btn" onclick="toggleSidebar()"><i data-lucide="menu"></i></button>
  </div>

  <div class="app-layout">
    <!-- Sidebar Mobile Backdrop Overlay -->
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

    <!-- Left Collapsible Sidebar Navigation -->
    <div class="sidebar" id="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-brand-wrapper">
          <img src="/assets/logo.png" alt="NetSage AI" class="sidebar-logo">
          <div class="sidebar-title-group">
            <h1>NetSage AI</h1>
            <div class="sidebar-caption">Cisco Troubleshooting</div>
          </div>
        </div>
        <button class="sidebar-toggle-btn" onclick="toggleSidebarCollapse()" title="Expand/Collapse Sidebar">
          <i data-lucide="panel-left-close" id="collapseIcon"></i>
        </button>
      </div>

      <div class="sidebar-nav">
        <div class="st-tab active" onclick="switchTab('explorer')" title="1. Case Explorer">
          <i data-lucide="search"></i>
          <span class="tab-label-text">1. Case Explorer</span>
        </div>
        <div class="st-tab" onclick="switchTab('ai-diagnosis')" title="2. AI Diagnosis">
          <i data-lucide="cpu"></i>
          <span class="tab-label-text">2. AI Diagnosis</span>
        </div>
        <div class="st-tab" onclick="switchTab('rule-checker')" title="3. Rule Checker">
          <i data-lucide="wrench"></i>
          <span class="tab-label-text">3. Rule Checker</span>
        </div>
        <div class="st-tab" onclick="switchTab('ai-comparison')" title="4. AI Comparison">
          <i data-lucide="git-compare"></i>
          <span class="tab-label-text">4. AI Comparison</span>
        </div>
        <div class="st-tab" onclick="switchTab('human-review')" title="5. Human Review">
          <i data-lucide="user-check"></i>
          <span class="tab-label-text">5. Human Review</span>
        </div>
        <div class="st-tab" onclick="switchTab('dashboard')" title="6. Dashboard">
          <i data-lucide="bar-chart-3"></i>
          <span class="tab-label-text">6. Dashboard</span>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="sidebar-footer-text">
          <div style="font-weight: 600; color: var(--text-main);">Deva Raj Bhojanapu</div>
          <div style="margin-top: 0.2rem; font-size: 0.72rem; color: #2563eb; font-weight: 600;">⚡ Vercel Serverless Ready</div>
        </div>
      </div>
    </div>

    <!-- Main Content Wrapper -->
    <div class="main-content">

      <!-- TAB 1: Case Explorer -->
      <div id="tab-explorer" class="tab-content active">
        <h2>Case Explorer</h2>
        <div class="st-caption" style="margin-bottom: 1rem;">Select a troubleshooting case to review its evidence.</div>

        <label>Choose a case:</label>
        <select id="caseSelect" onchange="onCaseChange()">
          <option value="">Loading cases...</option>
        </select>

        <div class="st-row" style="margin-top: 1rem;">
          <div class="st-col">
            <h3>Symptom</h3>
            <div class="st-alert st-info"><i data-lucide="info"></i><span id="c-symptom">-</span></div>

            <h3>Topology Note</h3>
            <div id="c-topo" style="color: var(--text-main); margin-bottom: 1.5rem; line-height: 1.5;">-</div>

            <h3>Show Output</h3>
            <div class="st-code" id="c-show">-</div>
          </div>

          <div class="st-col">
            <h3>Case Metadata</h3>
            <p style="margin-bottom: 0.5rem;"><strong>OSI Layer:</strong> <span id="c-osi">-</span></p>
            <p style="margin-bottom: 0.5rem;"><strong>Concept Tag:</strong> <span id="c-cat">-</span></p>
            <p style="margin-bottom: 1.5rem;"><strong>Severity:</strong> <span id="c-sev">-</span></p>

            <h3>Expected Fault (known answer)</h3>
            <div class="st-alert st-success"><i data-lucide="check-circle-2"></i><span id="c-exp">-</span></div>
            <div class="st-caption">The expected fault is the known-correct answer used for grading the AI's diagnosis. In a real NOC this would not be shown to the AI, only used afterward for comparison.</div>
          </div>
        </div>
      </div>

      <!-- TAB 2: AI Diagnosis -->
      <div id="tab-ai-diagnosis" class="tab-content">
        <h2>AI Diagnosis</h2>
        <div class="st-caption">Selected case: <strong id="t2-case-id">-</strong></div>
        <div class="st-caption" style="margin-bottom: 1rem;">This uses a mock AI function (ai/diagnosis.py) that returns realistic, structured JSON — no API key required. See prompts/diagnose_prompt.md for the prompt design this mock is standing in for.</div>

        <button class="st-btn" onclick="runAIDiagnosis()"><i data-lucide="cpu"></i> Run AI Diagnosis</button>

        <div id="ai-placeholder" class="st-alert st-info"><i data-lucide="info"></i><span>Click 'Run AI Diagnosis' to generate a structured diagnosis for this case.</span></div>

        <div id="ai-results" style="display:none;">
          <h3>Structured AI Output</h3>
          <p style="margin-bottom: 0.5rem;"><strong>Root Cause:</strong> <span id="ai-rc">-</span></p>
          <p style="margin-bottom: 0.5rem;"><strong>Confidence:</strong> <span id="ai-conf" style="font-weight: 600;">-</span></p>
          <p style="margin-bottom: 0.5rem;"><strong>Evidence:</strong> <span id="ai-ev">-</span></p>
          <p style="margin-top: 1rem; margin-bottom: 0.4rem;"><strong>Suggested Next Command:</strong></p>
          <div class="st-code" id="ai-cmd" style="padding: 0.5rem 0.8rem; margin-bottom: 1rem;">-</div>

          <p style="margin-bottom: 0.4rem;"><strong>Fix Steps:</strong></p>
          <ol id="ai-steps" style="margin-left: 1.5rem; margin-bottom: 1.5rem; line-height: 1.6;"></ol>

          <div class="st-alert st-warning">
            <i data-lucide="alert-triangle"></i>
            <span>This AI diagnosis is a draft and REQUIRES HUMAN REVIEW before being applied to production network equipment. Go to the <strong>Human Review</strong> tab to accept, edit, or reject this answer.</span>
          </div>
        </div>
      </div>

      <!-- TAB 3: Rule Checker -->
      <div id="tab-rule-checker" class="tab-content">
        <h2>Rule Checker (Deterministic, Non-AI)</h2>
        <div class="st-caption">Selected case: <strong id="t3-case-id">-</strong></div>
        <div class="st-caption" style="margin-bottom: 1rem;">This runs plain Python logic (checker/rule_checker.py) against the case's show output — no AI involved. It checks for duplicate IPs, wrong subnet masks, gateway mismatches, interface-down states, missing VLANs, and missing routes.</div>

        <button class="st-btn" onclick="runRuleChecker()"><i data-lucide="search"></i> Run Rule Checker</button>

        <div id="checker-placeholder" class="st-alert st-info"><i data-lucide="info"></i><span>Click 'Run Rule Checker' to evaluate this case with deterministic checks.</span></div>
        <div id="checker-list"></div>
      </div>

      <!-- TAB 4: AI Comparison -->
      <div id="tab-ai-comparison" class="tab-content">
        <h2>AI Comparison</h2>
        <div class="st-caption">Selected case: <strong id="t4-case-id">-</strong></div>
        <div class="st-caption" style="margin-bottom: 1rem;">Compares the AI diagnosis's root cause with the case's known expected_fault, and classifies the result as Match, Partial Match, or No Match, based on shared technical keywords.</div>

        <div id="comp-initial-info" class="st-alert st-info"><i data-lucide="info"></i><span>Run the AI Diagnosis (Tab 2) first, then come back here to compare it.</span></div>

        <div id="comp-btn-wrapper" style="display:none;">
          <button class="st-btn" onclick="runComparison()"><i data-lucide="scale"></i> Compare AI Diagnosis to Expected Fault</button>
        </div>

        <div id="comp-results" style="display:none; margin-top: 1rem;">
          <h3 id="comp-header-title">Match</h3>
          <div class="st-row" style="margin-top: 1rem;">
            <div class="st-col">
              <p><strong>AI Root Cause:</strong></p>
              <p id="comp-ai-text" style="color: var(--text-muted); margin-top: 0.25rem;">-</p>
            </div>
            <div class="st-col">
              <p><strong>Expected Fault (known answer):</strong></p>
              <p id="comp-exp-text" style="color: var(--text-muted); margin-top: 0.25rem;">-</p>
            </div>
          </div>
          <p style="margin-top: 1rem;"><strong>Overlapping keywords:</strong> <span id="comp-keywords" style="color: var(--text-muted);">-</span></p>
        </div>
      </div>

      <!-- TAB 5: Human Review -->
      <div id="tab-human-review" class="tab-content">
        <h2>Human Review</h2>
        <div class="st-caption">Selected case: <strong id="t5-case-id">-</strong></div>
        <div class="st-caption" style="margin-bottom: 1rem;">A human reviewer must Accept, Edit, or Reject every AI diagnosis before it is treated as final. All decisions are logged to logs/responsible_ai_log.csv for auditability.</div>

        <div id="rev-no-ai" class="st-alert st-info"><i data-lucide="info"></i><span>Run the AI Diagnosis (Tab 2) first — there's nothing to review yet.</span></div>

        <div id="rev-form-container" style="display:none;">
          <p style="margin-bottom: 0.25rem;"><strong>AI Root Cause being reviewed:</strong></p>
          <p id="rev-ai-cause" style="margin-bottom: 1rem; color: var(--text-muted);">-</p>

          <label>Reviewer decision:</label>
          <div class="radio-group">
            <label class="radio-label"><input type="radio" name="revStatus" value="Accepted" checked onchange="toggleCorrectedField()"> Accepted</label>
            <label class="radio-label"><input type="radio" name="revStatus" value="Edited" onchange="toggleCorrectedField()"> Edited</label>
            <label class="radio-label"><input type="radio" name="revStatus" value="Rejected" onchange="toggleCorrectedField()"> Rejected</label>
          </div>

          <label>Reviewer notes (optional but recommended):</label>
          <textarea id="revNotes" rows="3" placeholder=""></textarea>

          <div id="corrected-field-wrap" style="display:none;">
            <label>Corrected answer (required for Edited/Rejected):</label>
            <textarea id="revCorrected" rows="3" placeholder=""></textarea>
          </div>

          <button class="st-btn" onclick="submitReview()"><i data-lucide="save"></i> Save Review to Log</button>
        </div>

        <hr>
        <h3>Review Log (most recent first)</h3>
        <div class="st-table-container">
          <table id="auditTable">
            <thead>
              <tr>
                <th>timestamp</th>
                <th>case_id</th>
                <th>ai_root_cause</th>
                <th>ai_confidence</th>
                <th>expected_fault</th>
                <th>comparison_result</th>
                <th>review_status</th>
                <th>corrected_answer</th>
                <th>reviewer_notes</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- TAB 6: Dashboard -->
      <div id="tab-dashboard" class="tab-content">
        <h2>Dashboard</h2>
        <div class="st-row" style="margin-bottom: 2rem;">
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">Total Cases</div><div class="st-metric-val" id="m-cases">0</div></div></div>
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">Total Reviews Logged</div><div class="st-metric-val" id="m-reviews">0</div></div></div>
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">AI-vs-Human Agreement</div><div class="st-metric-val" id="m-agreement">0%</div></div></div>
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">Accepted Reviews</div><div class="st-metric-val" id="m-accepted">0</div></div></div>
        </div>

        <hr>

        <div class="st-row">
          <div class="st-col">
            <h3>Cases by Concept Tag</h3>
            <canvas id="chartConcept" style="max-height:300px;"></canvas>
          </div>
          <div class="st-col">
            <h3>Cases by Severity</h3>
            <canvas id="chartSeverity" style="max-height:300px;"></canvas>
          </div>
        </div>

        <hr>

        <div class="st-row">
          <div class="st-col">
            <h3>Review Outcome Breakdown</h3>
            <canvas id="chartReviewOutcome" style="max-height:280px;"></canvas>
          </div>
          <div class="st-col">
            <h3>AI vs Human Agreement Rate</h3>
            <canvas id="chartAgreement" style="max-height:280px;"></canvas>
          </div>
        </div>

        <hr>

        <div class="st-row">
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">Accepted</div><div class="st-metric-val" id="m-acc-total">0</div></div></div>
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">Edited</div><div class="st-metric-val" id="m-edi-total">0</div></div></div>
          <div class="st-col"><div class="st-metric-card"><div class="st-metric-label">Rejected</div><div class="st-metric-val" id="m-rej-total">0</div></div></div>
        </div>

      </div>

    </div> <!-- End Main Content -->
  </div> <!-- End App Layout -->

  <script>
    let casesData = [];
    let currentCase = null;
    let aiDiagnosisData = null;
    let comparisonData = null;

    function toggleSidebar() {
      const sb = document.getElementById('sidebar');
      const ov = document.getElementById('sidebarOverlay');
      sb.classList.toggle('open');
      ov.classList.toggle('open');
    }

    function toggleSidebarCollapse() {
      const sb = document.getElementById('sidebar');
      const icon = document.getElementById('collapseIcon');
      sb.classList.toggle('collapsed');
      
      if(sb.classList.contains('collapsed')) {
        icon.setAttribute('data-lucide', 'panel-left-open');
      } else {
        icon.setAttribute('data-lucide', 'panel-left-close');
      }
      lucide.createIcons();
    }

    async function init() {
      const res = await fetch('/api/cases');
      casesData = await res.json();
      const sel = document.getElementById('caseSelect');
      sel.innerHTML = '';
      casesData.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.case_id;
        opt.textContent = `${c.case_id} — ${c.concept_tag || 'General'} (${c.severity || 'Normal'})`;
        sel.appendChild(opt);
      });
      if(casesData.length > 0) onCaseChange();
      loadAuditLogs();
      loadDashboard();
      lucide.createIcons();
    }

    function onCaseChange() {
      const id = document.getElementById('caseSelect').value;
      currentCase = casesData.find(c => c.case_id === id);
      if(!currentCase) return;

      ['t2-case-id', 't3-case-id', 't4-case-id', 't5-case-id'].forEach(el => {
        const target = document.getElementById(el);
        if(target) target.textContent = currentCase.case_id;
      });

      document.getElementById('c-symptom').textContent = currentCase.symptom || '';
      document.getElementById('c-topo').textContent = currentCase.topology_note || 'N/A';
      document.getElementById('c-show').textContent = currentCase.show_outputs || 'No outputs';
      document.getElementById('c-osi').textContent = currentCase.osi_layer || 'N/A';
      document.getElementById('c-cat').textContent = currentCase.concept_tag || 'N/A';
      document.getElementById('c-sev').textContent = currentCase.severity || 'N/A';
      document.getElementById('c-exp').textContent = currentCase.expected_fault || 'N/A';

      document.getElementById('ai-placeholder').style.display = 'flex';
      document.getElementById('ai-results').style.display = 'none';
      document.getElementById('checker-placeholder').style.display = 'flex';
      document.getElementById('checker-list').innerHTML = '';
      
      document.getElementById('comp-initial-info').style.display = 'flex';
      document.getElementById('comp-btn-wrapper').style.display = 'none';
      document.getElementById('comp-results').style.display = 'none';

      document.getElementById('rev-no-ai').style.display = 'flex';
      document.getElementById('rev-form-container').style.display = 'none';

      aiDiagnosisData = null;
      comparisonData = null;
      setTimeout(() => lucide.createIcons(), 50);
    }

    function switchTab(tab) {
      document.querySelectorAll('.st-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      const targetTab = Array.from(document.querySelectorAll('.st-tab')).find(t => t.getAttribute('onclick') && t.getAttribute('onclick').includes(`'${tab}'`));
      if(targetTab) targetTab.classList.add('active');

      document.getElementById(`tab-${tab}`).classList.add('active');

      const sb = document.getElementById('sidebar');
      const ov = document.getElementById('sidebarOverlay');
      if(sb.classList.contains('open')) {
        sb.classList.remove('open');
        ov.classList.remove('open');
      }

      if(tab === 'dashboard') loadDashboard();
      setTimeout(() => lucide.createIcons(), 50);
    }

    async function runAIDiagnosis() {
      if(!currentCase) return;
      const res = await fetch('/api/diagnose', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({case_id: currentCase.case_id})
      });
      aiDiagnosisData = await res.json();
      
      document.getElementById('ai-placeholder').style.display = 'none';
      document.getElementById('ai-results').style.display = 'block';

      document.getElementById('ai-rc').textContent = aiDiagnosisData.root_cause;
      
      const conf = aiDiagnosisData.confidence;
      const confEl = document.getElementById('ai-conf');
      confEl.textContent = conf;
      confEl.style.color = (conf === 'High' || conf >= 0.85) ? '#166534' : (conf === 'Medium' || conf >= 0.5) ? '#92400e' : '#991b1b';

      document.getElementById('ai-ev').textContent = Array.isArray(aiDiagnosisData.evidence) ? aiDiagnosisData.evidence.join(', ') : aiDiagnosisData.evidence;
      document.getElementById('ai-cmd').textContent = aiDiagnosisData.next_command || '-';

      const stepsList = document.getElementById('ai-steps');
      stepsList.innerHTML = '';
      (aiDiagnosisData.fix_steps || []).forEach(step => {
        const li = document.createElement('li');
        li.textContent = step;
        stepsList.appendChild(li);
      });

      document.getElementById('comp-initial-info').style.display = 'none';
      document.getElementById('comp-btn-wrapper').style.display = 'block';

      document.getElementById('rev-no-ai').style.display = 'none';
      document.getElementById('rev-form-container').style.display = 'block';
      document.getElementById('rev-ai-cause').textContent = aiDiagnosisData.root_cause;
      setTimeout(() => lucide.createIcons(), 50);
    }

    async function runRuleChecker() {
      if(!currentCase) return;
      const res = await fetch('/api/checker', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({case_id: currentCase.case_id})
      });
      const checks = await res.json();
      document.getElementById('checker-placeholder').style.display = 'none';
      const container = document.getElementById('checker-list');
      container.innerHTML = '';
      checks.forEach(c => {
        const div = document.createElement('div');
        div.className = `st-alert ${c.result === 'PASS' ? 'st-success' : 'st-error'}`;
        const iconName = c.result === 'PASS' ? 'check-circle' : 'x-circle';
        div.innerHTML = `<i data-lucide="${iconName}"></i><div><strong>${c.check}</strong> — ${c.detail}</div>`;
        container.appendChild(div);
      });
      setTimeout(() => lucide.createIcons(), 50);
    }

    async function runComparison() {
      if(!currentCase || !aiDiagnosisData) return;
      const res = await fetch('/api/compare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ai_root_cause: aiDiagnosisData.root_cause,
          expected_fault: currentCase.expected_fault
        })
      });
      comparisonData = await res.json();
      
      const iconMap = {
        'Match': '<i data-lucide="check-circle-2" style="color:#166534;"></i> Match',
        'Partial Match': '<i data-lucide="alert-circle" style="color:#92400e;"></i> Partial Match',
        'No Match': '<i data-lucide="x-circle" style="color:#991b1b;"></i> No Match'
      };
      document.getElementById('comp-header-title').innerHTML = iconMap[comparisonData.result] || comparisonData.result;
      document.getElementById('comp-ai-text').textContent = aiDiagnosisData.root_cause;
      document.getElementById('comp-exp-text').textContent = currentCase.expected_fault || 'N/A';
      document.getElementById('comp-keywords').textContent = (comparisonData.overlapping_keywords || []).join(', ') || 'None';
      document.getElementById('comp-results').style.display = 'block';
      setTimeout(() => lucide.createIcons(), 50);
    }

    function toggleCorrectedField() {
      const val = document.querySelector('input[name="revStatus"]:checked').value;
      document.getElementById('corrected-field-wrap').style.display = (val === 'Edited' || val === 'Rejected') ? 'block' : 'none';
    }

    async function submitReview() {
      if(!currentCase || !aiDiagnosisData) return;
      const status = document.querySelector('input[name="revStatus"]:checked').value;
      const corrected = document.getElementById('revCorrected').value;
      const notes = document.getElementById('revNotes').value;

      if((status === 'Edited' || status === 'Rejected') && !corrected.trim()) {
        alert('Please provide a corrected answer for an Edited or Rejected review.');
        return;
      }

      const payload = {
        case_id: currentCase.case_id,
        ai_root_cause: aiDiagnosisData.root_cause,
        ai_confidence: aiDiagnosisData.confidence,
        expected_fault: currentCase.expected_fault || '',
        comparison_result: comparisonData ? comparisonData.result : '',
        review_status: status,
        corrected_answer: corrected,
        reviewer_notes: notes
      };

      await fetch('/api/review', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      alert(`Review saved for case ${currentCase.case_id} — status: ${status}`);
      loadAuditLogs();
      loadDashboard();
    }

    async function loadAuditLogs() {
      const res = await fetch('/api/reviews');
      const logs = await res.json();
      const tbody = document.querySelector('#auditTable tbody');
      tbody.innerHTML = '';
      logs.forEach(l => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${l.timestamp}</td>
          <td>${l.case_id}</td>
          <td>${l.ai_root_cause}</td>
          <td>${l.ai_confidence}</td>
          <td>${l.expected_fault}</td>
          <td>${l.comparison_result}</td>
          <td>${l.review_status}</td>
          <td>${l.corrected_answer}</td>
          <td>${l.reviewer_notes}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    let chartConcept, chartSev, chartOutcome, chartAgreed;
    async function loadDashboard() {
      const res = await fetch('/api/dashboard');
      const data = await res.json();

      document.getElementById('m-cases').textContent = data.total_cases;
      document.getElementById('m-reviews').textContent = data.total_reviews;
      document.getElementById('m-agreement').textContent = `${data.agreement_rate}%`;
      document.getElementById('m-accepted').textContent = data.accepted_reviews;

      document.getElementById('m-acc-total').textContent = data.accepted_reviews;
      document.getElementById('m-edi-total').textContent = data.edited_reviews;
      document.getElementById('m-rej-total').textContent = data.rejected_reviews;

      if(chartConcept) chartConcept.destroy();
      if(chartSev) chartSev.destroy();
      if(chartOutcome) chartOutcome.destroy();
      if(chartAgreed) chartAgreed.destroy();

      const ctxC = document.getElementById('chartConcept').getContext('2d');
      chartConcept = new Chart(ctxC, {
        type: 'bar',
        data: {
          labels: Object.keys(data.concept_counts),
          datasets: [{
            label: 'Cases',
            data: Object.values(data.concept_counts),
            backgroundColor: '#2563eb',
            borderRadius: 3
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { color: '#e2e8f0' },
              ticks: { maxRotation: 45, minRotation: 45, font: { family: 'Inter, sans-serif', size: 11 } }
            },
            y: {
              min: 0,
              max: 3.0,
              ticks: { stepSize: 0.5, font: { family: 'Inter, sans-serif', size: 11 } },
              grid: { color: '#e2e8f0' }
            }
          }
        }
      });

      const ctxS = document.getElementById('chartSeverity').getContext('2d');
      const sevColors = { 'High': '#ef4444', 'Low': '#f59e0b', 'Medium': '#22c55e' };
      const sevLabels = Object.keys(data.severity_counts);
      const sevData = Object.values(data.severity_counts);
      const sevBg = sevLabels.map(l => sevColors[l] || '#3b82f6');
      chartSev = new Chart(ctxS, {
        type: 'doughnut',
        data: {
          labels: sevLabels,
          datasets: [{
            data: sevData,
            backgroundColor: sevBg,
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          cutout: '55%',
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: { font: { family: 'Inter, sans-serif', size: 12 }, usePointStyle: true, boxWidth: 8 }
            }
          }
        }
      });

      const ctxO = document.getElementById('chartReviewOutcome').getContext('2d');
      chartOutcome = new Chart(ctxO, {
        type: 'doughnut',
        data: {
          labels: ['Accepted', 'Edited', 'Rejected'],
          datasets: [{
            data: [data.accepted_reviews, data.edited_reviews, data.rejected_reviews],
            backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          cutout: '55%',
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: { font: { family: 'Inter, sans-serif', size: 12 }, usePointStyle: true, boxWidth: 8 }
            }
          }
        }
      });

      const ctxA = document.getElementById('chartAgreement').getContext('2d');
      chartAgreed = new Chart(ctxA, {
        type: 'doughnut',
        data: {
          labels: ['Agreed (Accepted)', 'Disagreed'],
          datasets: [{
            data: [data.accepted_reviews, data.total_reviews - data.accepted_reviews],
            backgroundColor: ['#22c55e', '#ef4444'],
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          cutout: '55%',
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: { font: { family: 'Inter, sans-serif', size: 12 }, usePointStyle: true, boxWidth: 8 }
            }
          }
        }
      });
    }


    window.onload = init;
  </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(PERFECT_RESPONSIVE_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
