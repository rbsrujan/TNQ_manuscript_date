"""
Confidence scoring engine for ManuSure.
Implements documented, deterministic scoring based on label strength,
contextual proximity, format ambiguity, calendar validity, and candidate agreement.
"""

from typing import List, Tuple
from .models import ConfidenceLevel, DateCandidate, ExtractionStatus


HIGH_THRESHOLD = 0.80
MEDIUM_THRESHOLD = 0.50


def compute_candidate_score(
    role: str,
    label_pattern: str,
    format_type: str,
    is_calendar_valid: bool,
    is_ambiguous_numeric: bool,
    source: str = "paragraph",
) -> float:
    """
    Computes a base confidence score (0.0 to 1.0) for an individual date candidate.
    """
    if not is_calendar_valid or is_ambiguous_numeric:
        return 0.0

    if role != "RECEIVED":
        return 0.0

    # Base score determined by label strength and pattern
    # Explicit direct label e.g. "Received:", "Date received:", "Manuscript received:"
    if label_pattern in ("EXPLICIT_RECEIVED", "DATE_RECEIVED", "MANUSCRIPT_RECEIVED", "REC_ABBR"):
        base_score = 0.95 if label_pattern != "REC_ABBR" else 0.85
    # Sentence-based context e.g. "This manuscript was received on..."
    elif label_pattern == "SENTENCE_RECEIVED":
        base_score = 0.85
    # Passive or weaker context e.g. "Received on"
    elif label_pattern == "RECEIVED_ON":
        base_score = 0.90
    else:
        base_score = 0.70

    # Format quality bonus / penalty
    # Full textual month or ISO is unambiguous
    if format_type in ("TEXT_FULL", "ISO"):
        base_score += 0.05
    elif format_type == "TEXT_ABBR":
        base_score += 0.03
    elif format_type == "NUMERIC_UNAMBIGUOUS":
        # Day > 12 so numeric is unambiguous, but pure numeric is slightly less clear than text
        base_score += 0.00

    # Structural location bonus
    if source in ("header", "header_table", "table_row", "table_cell"):
        base_score += 0.02

    # Cap score strictly between 0.0 and 1.0
    return min(1.0, max(0.0, round(base_score, 2)))


def score_extraction_result(
    candidates: List[DateCandidate],
    conflicting: bool = False,
) -> Tuple[float, ConfidenceLevel, ExtractionStatus, str]:
    """
    Evaluates all received candidates in a document, resolves candidate agreement,
    and returns (confidence_score, confidence_level, extraction_status, reason).
    """
    if conflicting:
        return 0.0, ConfidenceLevel.LOW, ExtractionStatus.CONFLICTING_DATES, "Conflicting received dates detected"

    if not candidates:
        return 0.0, ConfidenceLevel.LOW, ExtractionStatus.NO_RECEIVED_DATE, "No received date label identified"

    # Inspect first candidate
    cand = candidates[0]

    if not cand.is_calendar_valid:
        return 0.0, ConfidenceLevel.LOW, ExtractionStatus.INVALID_CALENDAR_DATE, f"Invalid calendar date: {cand.raw_text}"

    if cand.is_ambiguous_numeric:
        return 0.0, ConfidenceLevel.LOW, ExtractionStatus.AMBIGUOUS_DATE, f"Ambiguous numeric date without established convention: {cand.raw_text}"

    score = cand.confidence_score

    # Agreement bonus if multiple independent mentions agreed on the exact same date
    if len(candidates) > 1:
        score = min(1.0, score + 0.05)

    score = round(score, 2)

    if score >= HIGH_THRESHOLD:
        level = ConfidenceLevel.HIGH
    elif score >= MEDIUM_THRESHOLD:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    status = ExtractionStatus.SUCCESS if score >= MEDIUM_THRESHOLD else ExtractionStatus.NO_RECEIVED_DATE
    reason = f"Identified received date with {level.value.lower()} confidence ({score})"

    return score, level, status, reason
