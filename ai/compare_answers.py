"""
ai/compare_answers.py
-----------------------
Compares the AI's root_cause text against the case's expected_fault
(the known correct answer for that case) and classifies the result as:

    "Match"          - the AI's root cause clearly matches the expected fault
    "Partial Match"  - some overlap, but not a full match
    "No Match"       - little or no overlap

This is a simple word-overlap comparison, which is easy for a beginner
to understand and explain in a demo, and is deterministic (no randomness).
"""

import re

# Common English/networking "filler" words we ignore when comparing,
# so the comparison focuses on the meaningful technical words.
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "on", "in", "of", "to",
    "for", "and", "or", "with", "at", "by", "from", "this", "that", "it",
    "its", "be", "not", "no", "so", "as", "than", "then", "which", "does",
    "do", "did", "has", "have", "had", "due", "caused", "cause", "causing",
    "issue", "problem",
}


def _tokenize(text: str) -> set:
    """Lowercase, strip punctuation, split into words, and remove stopwords."""
    words = re.findall(r"[a-z0-9/.]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def compare_diagnosis(ai_root_cause: str, expected_fault: str) -> str:
    """
    Compare the AI diagnosis root cause with the expected fault text.

    Returns one of: "Match", "Partial Match", "No Match"
    """
    ai_words = _tokenize(ai_root_cause or "")
    expected_words = _tokenize(expected_fault or "")

    if not expected_words:
        return "No Match"

    overlap = ai_words & expected_words
    overlap_ratio = len(overlap) / len(expected_words)

    if overlap_ratio >= 0.5:
        return "Match"
    elif overlap_ratio >= 0.2:
        return "Partial Match"
    else:
        return "No Match"


def get_comparison_details(ai_root_cause: str, expected_fault: str) -> dict:
    """
    Returns the match result plus the overlapping keywords, useful for
    displaying "why" a match/partial match/no match was decided in the UI.
    """
    ai_words = _tokenize(ai_root_cause or "")
    expected_words = _tokenize(expected_fault or "")
    overlap = sorted(ai_words & expected_words)

    return {
        "result": compare_diagnosis(ai_root_cause, expected_fault),
        "overlapping_keywords": overlap,
    }
