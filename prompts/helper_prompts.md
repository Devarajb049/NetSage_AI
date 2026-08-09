# NetSage AI - Helper Prompts

Supplementary prompt designs for future extensions of NetSage AI. These
are not required for the current mock version, but are included so a
real LLM integration can reuse the same structured approach as the main
diagnose prompt (see `diagnose_prompt.md`).

---

## 1. Comparison / Grading Prompt

Used to ask an LLM to compare the AI's `root_cause` against a case's
`expected_fault` and classify the result, as an alternative to the
simple keyword-overlap logic in `ai/compare_answers.py`.

```
System: You are grading a network diagnosis against a known-correct
answer. Given the AI's root cause and the expected fault, respond with
ONLY one word: "Match", "Partial Match", or "No Match".

- "Match": the AI identified the same underlying fault, even if worded
  differently.
- "Partial Match": the AI identified the right general area (e.g. the
  right device or protocol) but missed a key specific detail.
- "No Match": the AI's answer does not reflect the actual fault.

User:
AI root cause: {ai_root_cause}
Expected fault: {expected_fault}
```

---

## 2. Reviewer Summary Prompt

Used to generate a short natural-language summary of a batch of human
review results, for example for a weekly NOC report.

```
System: You are summarizing a batch of human-reviewed AI network
diagnoses for a weekly report. Be concise (3-5 sentences), mention the
overall AI-vs-human agreement rate, call out any recurring issue types
that needed correction, and end with one suggestion for improving the
AI diagnosis prompt.

User:
Review log (case_id, review_status, comparison_result, concept_tag):
{review_log_rows}
```

---

## 3. New Case Intake Prompt

Used if you want an LLM to help convert a raw incident report (e.g. a
help-desk ticket) into the structured case format used by
`data/cases.csv`, so new cases can be added quickly.

```
System: You convert raw network incident reports into a structured
case record for a troubleshooting knowledge base. Extract or infer the
following fields ONLY from the text provided - if a field cannot be
determined, use "Unknown":

{
  "symptom": "...",
  "topology_note": "...",
  "show_outputs": "...",
  "expected_fault": "...",
  "osi_layer": "...",
  "concept_tag": "...",
  "severity": "Low | Medium | High | Critical"
}

User:
Raw incident report:
{raw_ticket_text}
```

---

## Responsible use reminder

Any output from these helper prompts should still go through the same
Human Review step used for the main diagnosis - AI output in NetSage
AI is always a *draft* for a human engineer, never an automatic action.
