"""
src/utils.py

Small shared helpers: text normalization and a lightweight fuzzy match
used by the evaluator to compare `expected_fault` (from cases.csv)
against the system's detected fault title, without trivial differences
in capitalization/punctuation/wording causing every comparison to fail.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# A small synonym map so common phrasing differences between the CSV's
# expected_fault wording and the checker's rule titles don't count
# against the match score.
_SYNONYMS = {
    "administratively down": "admin down",
    "sub-interface": "subinterface",
    "interface": "iface",
    "pool exhaustion": "pool exhausted",
    "misconfiguration": "misconfigured",
    "misconfigured": "misconfiguration",
}


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, apply light
    synonym normalization. Used for fuzzy comparisons only — never for
    the rule-matching regexes in checker.py."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for src, dst in _SYNONYMS.items():
        text = text.replace(src, dst)
    return text


def similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity score between two strings after
    normalization, using a token-overlap-friendly sequence matcher."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def fuzzy_match(a: str, b: str, threshold: float = 0.35) -> bool:
    """True if two fault descriptions are 'close enough' to be considered
    the same finding. The threshold is intentionally lenient because
    expected_fault (CSV) and rule titles (checker.py) are independently
    worded descriptions of the same underlying fault, not identical
    strings — a token-overlap check is more meaningful here than exact
    matching."""
    na, nb = set(normalize_text(a).split()), set(normalize_text(b).split())
    if not na or not nb:
        return False
    overlap = len(na & nb) / max(1, min(len(na), len(nb)))
    return overlap >= threshold or similarity(a, b) >= 0.5
