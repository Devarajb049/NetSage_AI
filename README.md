# NetSage AI

**AI-Assisted Cisco Network Troubleshooting System** — a beginner-friendly
Streamlit dashboard built as a Cisco internship submission.

NetSage AI lets a network engineer pick a troubleshooting case, get a
structured AI diagnosis, cross-check it against a deterministic
(non-AI) rule checker, compare the AI's answer to the known fault, and
log a human reviewer's Accept/Edit/Reject decision — with everything
summarized on a dashboard. It's a small demonstration of **Responsible
AI**: every AI output is clearly labeled as a draft that needs a human
in the loop.

---

## What's inside

| Feature | Description |
|---|---|
| **Case Explorer** | Browse 30 realistic Cisco troubleshooting cases (VLANs, gateways, DHCP, DNS, routing, ACLs, NAT, wireless, and more). |
| **AI Diagnosis** | Runs a mock AI function that returns structured JSON: root cause, confidence, evidence, next command, and fix steps. No API key needed. |
| **Rule Checker** | Plain Python logic (no AI) that checks for duplicate IPs, wrong subnet masks, gateway mismatches, interface-down states, missing VLANs, and missing routes. |
| **AI Comparison** | Compares the AI's root cause with the case's known `expected_fault` and classifies it as Match / Partial Match / No Match. |
| **Human Review** | A reviewer accepts, edits, or rejects the AI's answer. All decisions are logged for auditability. |
| **Dashboard** | Charts for cases by issue type, cases by severity, review outcomes, and AI-vs-human agreement rate. |

---

## Folder structure

```text
NetSage-AI/
├── app.py                      # Main Streamlit app (all 6 tabs)
├── requirements.txt
├── README.md
├── data/
│   └── cases.csv                # 30 sample troubleshooting cases
├── prompts/
│   ├── diagnose_prompt.md        # Structured prompt design for AI diagnosis
│   └── helper_prompts.md         # Extra prompts for future features
├── ai/
│   ├── diagnosis.py               # Mock AI diagnosis function (swap for real LLM later)
│   └── compare_answers.py         # AI-vs-expected-fault comparison logic
├── checker/
│   ├── rule_checker.py            # Deterministic (non-AI) rule checks
│   └── sample_output.txt          # Example checker output on several cases
├── logs/
│   └── responsible_ai_log.csv     # Human review log (pre-seeded with 8 sample reviews)
└── dashboard/
    └── charts.py                  # Plotly chart-building functions
```

---

## Setup

1. **Install dependencies** (Python 3.9+ recommended):

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app:**

   ```bash
   streamlit run app.py
   ```

3. Streamlit will open the dashboard in your browser (usually at
   `http://localhost:8501`).

No API key or account signup is required — the AI diagnosis is fully
mocked for this version.

---

## Vercel Deployment

This project includes native Vercel Serverless Function support via `api/index.py` and `vercel.json`.

1. **Deploy via Vercel CLI:**
   ```bash
   vercel
   ```
2. Or import this GitHub repository (`Devarajb049/NetSage_AI`) directly into your Vercel Dashboard. Vercel will automatically detect `vercel.json` and deploy the full serverless API & dashboard!

---

## How the "AI" works right now (and how to upgrade it later)

`ai/diagnosis.py` contains a **mock AI function**, `get_ai_diagnosis()`.
It scans the case's symptom/topology/show-output text for keywords and
returns a realistic structured diagnosis (root cause, confidence,
evidence, next command, fix steps) — the same shape a real LLM call
would return.

The structured prompt this mock stands in for is fully written out in
`prompts/diagnose_prompt.md`. To connect a real LLM later:

1. Keep the function signature `get_ai_diagnosis(case: dict) -> dict`.
2. Inside the function, call the Anthropic API using the system prompt
   and user message template from `prompts/diagnose_prompt.md`.
3. Parse the JSON response into the same 5 fields.
4. `app.py` does not need any changes — it only calls this function.

---

## Deterministic rule checker

`checker/rule_checker.py` is **not AI** — it's plain Python pattern
matching against each case's `show_outputs` text, checking for:

- Duplicate IP addresses
- Wrong/suspicious subnet masks
- Gateway mismatches (client default gateway vs. actual SVI IP)
- Interfaces that are down / administratively down / err-disabled
- Missing VLANs (referenced but not created)
- Missing routes (expected subnet not present in the routing table)

Run it directly for a quick demo:

```bash
python checker/rule_checker.py
```

See `checker/sample_output.txt` for example output across several
cases.

---

## Responsible AI log

`logs/responsible_ai_log.csv` records every human review decision:
timestamp, case ID, the AI's root cause and confidence, the expected
fault, the comparison result, the reviewer's status (Accepted / Edited
/ Rejected), any corrected answer, and reviewer notes.

The file comes pre-seeded with **8 sample review records**, including
**5 with human corrections** (3 Edited, 2 Rejected), so the Dashboard
tab has meaningful data to show right away. New reviews submitted from
the app are appended to the same file.

---

## Demo video guide (5–10 minutes)

Suggested walkthrough if you're recording a demo video for your
internship submission:

1. **Intro (30s)** — State the problem: NOC engineers spend time
   manually diagnosing repetitive network issues; NetSage AI shows how
   an AI-assisted (but human-reviewed) workflow could help.
2. **Case Explorer (1 min)** — Pick 1–2 cases, show the symptom,
   topology note, show output, and expected fault. Mention there are
   30 cases spanning VLANs, routing, DNS, DHCP, ACLs, NAT, wireless, etc.
3. **AI Diagnosis (1–2 min)** — Click "Run AI Diagnosis" on a case (try
   the duplicate-IP case, C001, since it's a clean example). Walk
   through the structured output: root cause, confidence, evidence,
   next command, fix steps. Point out the human-review warning.
4. **Rule Checker (1–2 min)** — Run the deterministic checker on the
   same case. Explain that this is plain Python, not AI, and show how
   it independently confirms (or could contradict) the AI's finding.
5. **AI Comparison (1 min)** — Show the Match / Partial Match / No
   Match result against the known expected fault.
6. **Human Review (1–2 min)** — Submit a review (try an "Edited"
   review to show the corrected-answer field), then scroll the review
   log table.
7. **Dashboard (1–2 min)** — Show the charts: cases by issue type,
   cases by severity, review outcomes, and AI-vs-human agreement rate.
   Mention the pre-seeded 8 sample reviews as a starting dataset.
8. **Wrap-up (30s)** — Mention the mock-AI-to-real-LLM upgrade path
   (`prompts/diagnose_prompt.md`) and that this was built with
   Responsible AI principles: every AI answer requires human review
   and is logged for auditability.

---

## Notes

- This is intentionally kept simple: no login/authentication, no
  database, no cloud deployment, and no payment features — just a
  local Streamlit app backed by CSV files, as specified for this
  beginner student project.
- All code is commented for a student new to Python/Streamlit.

## Known limitations (good talking points for the demo)

- **Rule checker is a simple heuristic.** The Duplicate IP check counts
  any IP address string that appears more than once in `show_outputs`.
  On a few cases (e.g. C002, C020, C028) the *same* IP legitimately
  appears twice (like a correctly-matching gateway and SVI address),
  so it's flagged as a false positive "duplicate." This is a good
  example to mention in a demo: deterministic checks are explainable
  but not perfect, which is exactly why the AI diagnosis and the human
  review step both still matter.
- **Mock AI has no rule for every concept.** `ai/diagnosis.py` uses a
  keyword-matching rule list, not a real model, so a few cases (e.g.
  C019 - VPN/IPsec, C022 - missing OSPF network statement) don't match
  any rule and fall back to a low-confidence "unable to determine"
  answer. See `logs/responsible_ai_log.csv` for how a human reviewer
  caught and corrected exactly this gap — a real demonstration of why
  human review matters, not just a disclaimer.
