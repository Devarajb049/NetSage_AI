import os
import csv
import json
from datetime import datetime
import pandas as pd
from flask import Flask, jsonify, request, render_template_string

# Import existing domain logic
from ai.diagnosis import get_ai_diagnosis
from ai.compare_answers import get_comparison_details
from checker.rule_checker import run_all_checks

app = Flask(__name__)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_CSV = os.path.join(HERE, "data", "cases.csv")
LOG_CSV = os.path.join(HERE, "logs", "responsible_ai_log.csv")
LOG_DIR = os.path.dirname(LOG_CSV)

LOG_FIELDNAMES = [
    "timestamp", "case_id", "ai_root_cause", "ai_confidence",
    "expected_fault", "comparison_result", "review_status",
    "corrected_answer", "reviewer_notes"
]

def load_cases_df():
    if os.path.exists(CASES_CSV):
        return pd.read_csv(CASES_CSV, dtype=str).fillna("")
    return pd.DataFrame()

def load_review_log_df():
    if not os.path.exists(LOG_CSV) or os.path.getsize(LOG_CSV) == 0:
        return pd.DataFrame(columns=LOG_FIELDNAMES)
    try:
        return pd.read_csv(LOG_CSV, dtype=str).fillna("")
    except Exception:
        with open(LOG_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader]
        return pd.DataFrame(rows, columns=LOG_FIELDNAMES).fillna("")

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

    # Cases by Concept/Tag
    concept_counts = {}
    if "concept_tag" in cases_df.columns:
        concept_counts = cases_df["concept_tag"].value_counts().to_dict()

    # Cases by Severity
    severity_counts = {}
    if "severity" in cases_df.columns:
        severity_counts = cases_df["severity"].value_counts().to_dict()

    # Review status
    review_status_counts = {}
    if "review_status" in reviews_df.columns and not reviews_df.empty:
        review_status_counts = reviews_df["review_status"].value_counts().to_dict()

    # Agreement rate
    total_reviews = len(reviews_df)
    accepted_reviews = len(reviews_df[reviews_df["review_status"] == "Accepted"]) if total_reviews > 0 else 0
    agreement_rate = round((accepted_reviews / total_reviews * 100), 1) if total_reviews > 0 else 0.0

    return jsonify({
        "total_cases": len(cases_df),
        "total_reviews": total_reviews,
        "agreement_rate": agreement_rate,
        "concept_counts": concept_counts,
        "severity_counts": severity_counts,
        "review_status_counts": review_status_counts
    })

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NetSage AI - Cisco Troubleshooting System</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      --card-bg: rgba(30, 41, 59, 0.7);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg-gradient);
      color: var(--text-main);
      min-height: 100vh;
      padding: 2rem;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--card-border);
    }
    .header h1 {
      font-size: 1.8rem;
      font-weight: 700;
      background: linear-gradient(90deg, #818cf8, #c084fc);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .header p { color: var(--text-muted); font-size: 0.9rem; margin-top: 0.25rem; }
    
    .nav-tabs {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      background: rgba(15, 23, 42, 0.6);
      padding: 0.5rem;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      overflow-x: auto;
    }
    .nav-tab {
      padding: 0.6rem 1.2rem;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 500;
      font-size: 0.9rem;
      color: var(--text-muted);
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .nav-tab:hover { color: var(--text-main); background: rgba(255, 255, 255, 0.05); }
    .nav-tab.active {
      color: #fff;
      background: var(--accent);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
    .card {
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 1.5rem;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    }
    .card h3 { font-size: 1.1rem; margin-bottom: 1rem; color: #e2e8f0; display: flex; align-items: center; gap: 0.5rem; }

    select, input, textarea, button {
      width: 100%;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      background: rgba(15, 23, 42, 0.8);
      color: #fff;
      font-family: inherit;
      margin-bottom: 1rem;
    }
    button {
      background: var(--accent);
      color: #fff;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: background 0.2s ease;
    }
    button:hover { background: var(--accent-hover); }

    .badge {
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-high { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-medium { background: rgba(245, 158, 11, 0.2); color: #fde047; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-low { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.4); }

    pre {
      background: rgba(15, 23, 42, 0.9);
      padding: 1rem;
      border-radius: 8px;
      font-family: monospace;
      font-size: 0.85rem;
      color: #cbd5e1;
      overflow-x: auto;
      border: 1px solid var(--card-border);
    }
    
    .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 1.25rem;
      border-radius: 12px;
      text-align: center;
    }
    .stat-card .val { font-size: 1.8rem; font-weight: 700; color: #818cf8; }
    .stat-card .lbl { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }

    table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.85rem; }
    th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--card-border); }
    th { color: var(--text-muted); font-weight: 600; }
  </style>
</head>
<body>

  <div class="header">
    <div>
      <h1>🛰️ NetSage AI</h1>
      <p>AI-Assisted Cisco Network Troubleshooting System & Audit Dashboard</p>
    </div>
    <div style="font-size: 0.85rem; color: var(--text-muted);">
      Vercel Serverless Ready
    </div>
  </div>

  <div class="nav-tabs">
    <div class="nav-tab active" onclick="switchTab('explorer')">🔍 Case Explorer</div>
    <div class="nav-tab" onclick="switchTab('ai-diagnosis')">🤖 AI Diagnosis</div>
    <div class="nav-tab" onclick="switchTab('rule-checker')">🛠️ Rule Checker</div>
    <div class="nav-tab" onclick="switchTab('ai-comparison')">⚖️ AI Comparison</div>
    <div class="nav-tab" onclick="switchTab('human-review')">✍️ Human Review</div>
    <div class="nav-tab" onclick="switchTab('dashboard')">📊 Dashboard & Analytics</div>
  </div>

  <div class="card" style="margin-bottom: 1.5rem;">
    <label style="font-size: 0.9rem; font-weight: 500; color: var(--text-muted); margin-bottom: 0.5rem; display: block;">Select Troubleshooting Case:</label>
    <select id="caseSelect" onchange="onCaseChange()">
      <option value="">Loading cases...</option>
    </select>
  </div>

  <!-- Tab 1: Case Explorer -->
  <div id="tab-explorer" class="tab-content active">
    <div class="grid">
      <div class="card">
        <h3>📋 Case Metadata</h3>
        <p><strong>Case ID:</strong> <span id="c-id">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Title:</strong> <span id="c-title">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Category:</strong> <span id="c-cat" class="badge badge-low">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Severity:</strong> <span id="c-sev" class="badge badge-medium">-</span></p>
        <p style="margin-top:1rem;"><strong>Symptom:</strong></p>
        <p id="c-symptom" style="color: var(--text-muted); font-size: 0.9rem; margin-top:0.25rem;">-</p>
      </div>
      <div class="card">
        <h3>🌐 Topology & Commands</h3>
        <p><strong>Topology Note:</strong></p>
        <p id="c-topo" style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">-</p>
        <p><strong>Show Outputs:</strong></p>
        <pre id="c-show">-</pre>
      </div>
    </div>
  </div>

  <!-- Tab 2: AI Diagnosis -->
  <div id="tab-ai-diagnosis" class="tab-content">
    <div class="card">
      <button onclick="runAIDiagnosis()">⚡ Run AI Diagnosis</button>
      <div id="ai-results" style="display:none; margin-top:1rem;">
        <h3>🤖 AI Diagnosis Results</h3>
        <p><strong>Root Cause:</strong> <span id="ai-rc" style="color: #cbd5e1;">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Confidence:</strong> <span id="ai-conf" class="badge badge-medium">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Evidence:</strong> <span id="ai-ev" style="color: var(--text-muted);">-</span></p>
        <p style="margin-top:1rem;"><strong>Next Command:</strong></p>
        <pre id="ai-cmd">-</pre>
        <p style="margin-top:1rem;"><strong>Fix Steps:</strong></p>
        <ul id="ai-steps" style="margin-left:1.5rem; color: var(--text-muted); font-size:0.9rem;"></ul>
      </div>
    </div>
  </div>

  <!-- Tab 3: Rule Checker -->
  <div id="tab-rule-checker" class="tab-content">
    <div class="card">
      <button onclick="runRuleChecker()">🛠️ Run Deterministic Rule Checks</button>
      <div id="checker-results" style="display:none; margin-top:1rem;">
        <h3>Deterministic Rule Check Results</h3>
        <table id="checker-table">
          <thead>
            <tr>
              <th>Check</th>
              <th>Status</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Tab 4: AI Comparison -->
  <div id="tab-ai-comparison" class="tab-content">
    <div class="card">
      <button onclick="runComparison()">⚖️ Compare AI vs Known Expected Fault</button>
      <div id="comparison-results" style="display:none; margin-top:1rem;">
        <h3>Comparison Details</h3>
        <p><strong>AI Diagnosis:</strong> <span id="comp-ai">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Expected Fault:</strong> <span id="comp-exp">-</span></p>
        <p style="margin-top:1rem;"><strong>Match Score:</strong> <span id="comp-score" class="badge badge-high">-</span></p>
        <p style="margin-top:0.5rem;"><strong>Overlapping Keywords:</strong> <span id="comp-keywords" style="color: var(--text-muted);">-</span></p>
      </div>
    </div>
  </div>

  <!-- Tab 5: Human Review -->
  <div id="tab-human-review" class="tab-content">
    <div class="card">
      <h3>✍️ Submit Responsible AI Human Review</h3>
      <label>Review Decision:</label>
      <select id="revStatus">
        <option value="Accepted">Accepted - AI Diagnosis is correct</option>
        <option value="Edited">Edited - AI Diagnosis needed corrections</option>
        <option value="Rejected">Rejected - AI Diagnosis was incorrect</option>
      </select>

      <label>Corrected Answer (if Edited/Rejected):</label>
      <input type="text" id="revCorrected" placeholder="Enter corrected diagnosis...">

      <label>Reviewer Notes:</label>
      <textarea id="revNotes" rows="3" placeholder="Enter any notes or observations..."></textarea>

      <button onclick="submitReview()">Submit Audit Review</button>
    </div>

    <div class="card" style="margin-top:1.5rem;">
      <h3>📜 Past Audit Logs</h3>
      <div style="overflow-x:auto;">
        <table id="auditTable">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Case ID</th>
              <th>AI Root Cause</th>
              <th>Status</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Tab 6: Dashboard -->
  <div id="tab-dashboard" class="tab-content">
    <div class="stats-row">
      <div class="stat-card"><div class="val" id="stat-cases">0</div><div class="lbl">Total Cases</div></div>
      <div class="stat-card"><div class="val" id="stat-reviews">0</div><div class="lbl">Total Reviews</div></div>
      <div class="stat-card"><div class="val" id="stat-agreement">0%</div><div class="lbl">Agreement Rate</div></div>
      <div class="stat-card"><div class="val" style="color:#10b981;">Active</div><div class="lbl">Vercel Serverless</div></div>
    </div>

    <div class="grid">
      <div class="card">
        <h3>Cases by Category</h3>
        <canvas id="chartCategory"></canvas>
      </div>
      <div class="card">
        <h3>Cases by Severity</h3>
        <canvas id="chartSeverity"></canvas>
      </div>
    </div>
  </div>

  <script>
    let casesData = [];
    let currentCase = null;
    let aiDiagnosisData = null;

    async function init() {
      const res = await fetch('/api/cases');
      casesData = await res.json();
      const sel = document.getElementById('caseSelect');
      sel.innerHTML = '';
      casesData.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.case_id;
        opt.textContent = `${c.case_id} - ${c.title || c.symptom}`;
        sel.appendChild(opt);
      });
      if(casesData.length > 0) onCaseChange();
      loadAuditLogs();
      loadDashboard();
    }

    function onCaseChange() {
      const id = document.getElementById('caseSelect').value;
      currentCase = casesData.find(c => c.case_id === id);
      if(!currentCase) return;

      document.getElementById('c-id').textContent = currentCase.case_id;
      document.getElementById('c-title').textContent = currentCase.title || 'N/A';
      document.getElementById('c-cat').textContent = currentCase.concept_tag || 'General';
      document.getElementById('c-sev').textContent = currentCase.severity || 'Normal';
      document.getElementById('c-symptom').textContent = currentCase.symptom || '';
      document.getElementById('c-topo').textContent = currentCase.topology_note || 'N/A';
      document.getElementById('c-show').textContent = currentCase.show_outputs || 'No outputs';

      document.getElementById('ai-results').style.display = 'none';
      document.getElementById('checker-results').style.display = 'none';
      document.getElementById('comparison-results').style.display = 'none';
      aiDiagnosisData = null;
    }

    function switchTab(tab) {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById(`tab-${tab}`).classList.add('active');
      if(tab === 'dashboard') loadDashboard();
    }

    async function runAIDiagnosis() {
      if(!currentCase) return;
      const res = await fetch('/api/diagnose', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({case_id: currentCase.case_id})
      });
      aiDiagnosisData = await res.json();
      document.getElementById('ai-rc').textContent = aiDiagnosisData.root_cause;
      document.getElementById('ai-conf').textContent = aiDiagnosisData.confidence;
      document.getElementById('ai-ev').textContent = aiDiagnosisData.evidence;
      document.getElementById('ai-cmd').textContent = aiDiagnosisData.next_command;

      const stepsList = document.getElementById('ai-steps');
      stepsList.innerHTML = '';
      (aiDiagnosisData.fix_steps || []).forEach(step => {
        const li = document.createElement('li');
        li.textContent = step;
        stepsList.appendChild(li);
      });

      document.getElementById('ai-results').style.display = 'block';
    }

    async function runRuleChecker() {
      if(!currentCase) return;
      const res = await fetch('/api/checker', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({case_id: currentCase.case_id})
      });
      const checks = await res.json();
      const tbody = document.querySelector('#checker-table tbody');
      tbody.innerHTML = '';
      checks.forEach(c => {
        const tr = document.createElement('tr');
        const badgeClass = c.result === 'PASS' ? 'badge-low' : 'badge-high';
        tr.innerHTML = `<td>${c.check}</td><td><span class="badge ${badgeClass}">${c.result}</span></td><td>${c.detail}</td>`;
        tbody.appendChild(tr);
      });
      document.getElementById('checker-results').style.display = 'block';
    }

    async function runComparison() {
      if(!currentCase) return;
      if(!aiDiagnosisData) await runAIDiagnosis();
      const res = await fetch('/api/compare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ai_root_cause: aiDiagnosisData.root_cause,
          expected_fault: currentCase.expected_fault
        })
      });
      const comp = await res.json();
      document.getElementById('comp-ai').textContent = aiDiagnosisData.root_cause;
      document.getElementById('comp-exp').textContent = currentCase.expected_fault || 'N/A';
      document.getElementById('comp-score').textContent = comp.result;
      document.getElementById('comp-keywords').textContent = (comp.overlapping_keywords || []).join(', ') || 'None';
      document.getElementById('comparison-results').style.display = 'block';
    }

    async function submitReview() {
      if(!currentCase) return;
      if(!aiDiagnosisData) await runAIDiagnosis();

      const payload = {
        case_id: currentCase.case_id,
        ai_root_cause: aiDiagnosisData ? aiDiagnosisData.root_cause : '',
        ai_confidence: aiDiagnosisData ? aiDiagnosisData.confidence : '',
        expected_fault: currentCase.expected_fault || '',
        comparison_result: document.getElementById('comp-score').textContent || '',
        review_status: document.getElementById('revStatus').value,
        corrected_answer: document.getElementById('revCorrected').value,
        reviewer_notes: document.getElementById('revNotes').value
      };

      await fetch('/api/review', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      alert('Review recorded successfully!');
      loadAuditLogs();
    }

    async function loadAuditLogs() {
      const res = await fetch('/api/reviews');
      const logs = await res.json();
      const tbody = document.querySelector('#auditTable tbody');
      tbody.innerHTML = '';
      logs.slice(-10).reverse().forEach(l => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${l.timestamp}</td><td>${l.case_id}</td><td>${l.ai_root_cause}</td><td><span class="badge badge-low">${l.review_status}</span></td><td>${l.reviewer_notes}</td>`;
        tbody.appendChild(tr);
      });
    }

    let chartCat, chartSev;
    async function loadDashboard() {
      const res = await fetch('/api/dashboard');
      const data = await res.json();

      document.getElementById('stat-cases').textContent = data.total_cases;
      document.getElementById('stat-reviews').textContent = data.total_reviews;
      document.getElementById('stat-agreement').textContent = `${data.agreement_rate}%`;

      if(chartCat) chartCat.destroy();
      if(chartSev) chartSev.destroy();

      const ctxCat = document.getElementById('chartCategory').getContext('2d');
      chartCat = new Chart(ctxCat, {
        type: 'bar',
        data: {
          labels: Object.keys(data.concept_counts),
          datasets: [{
            label: 'Cases',
            data: Object.values(data.concept_counts),
            backgroundColor: '#818cf8'
          }]
        },
        options: { plugins: { legend: { display: false } } }
      });

      const ctxSev = document.getElementById('chartSeverity').getContext('2d');
      chartSev = new Chart(ctxSev, {
        type: 'doughnut',
        data: {
          labels: Object.keys(data.severity_counts),
          datasets: [{
            data: Object.values(data.severity_counts),
            backgroundColor: ['#ef4444', '#f59e0b', '#10b981', '#6366f1']
          }]
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
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
