"""
Rule-based NLP Extraction and Semantic Classification for ManuSure.
Analyzes text context around candidate dates, identifies semantic roles,
resolves candidate conflicts, and determines the manuscript received date.
"""

import re
from typing import List, Optional, Tuple

from .confidence import compute_candidate_score, score_extraction_result
from .date_validator import find_date_spans_in_text, parse_candidate_date_string
from .docx_reader import TextBlock
from .models import ConfidenceLevel, DateCandidate, ExtractionResult, ExtractionStatus

# Specific revision patterns (must be checked BEFORE generic received patterns)
RE_ROLE_REVISED = re.compile(
    r"\b(?:received\s+(?:in\s+)?revised\s+form|received\s+revised|revision\s+received|revised(?:\s+on)?|resubmitted(?:\s+on)?|revision(?:\s+date)?)\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

# Accepted patterns
RE_ROLE_ACCEPTED = re.compile(
    r"\b(?:accepted(?:\s+on)?|date\s+accepted|article\s+accepted|approved(?:\s+on)?)\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

# Published patterns
RE_ROLE_PUBLISHED = re.compile(
    r"\b(?:published(?:\s+online)?(?:\s+on)?|available\s+online(?:\s+on)?|e-published(?:\s+on)?|publication\s+date)\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

# Submitted patterns
RE_ROLE_SUBMITTED = re.compile(
    r"\b(?:submitted(?:\s+on)?|submission\s+date|date\s+submitted)\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

# Ambiguous label patterns (e.g. Date: 15 January 2025 without "received")
RE_ROLE_AMBIGUOUS = re.compile(
    r"\b(?:date|dated)\s*[:\-–—]\s*$",
    re.IGNORECASE,
)

# Explicit received patterns
RE_EXPLICIT_RECEIVED = re.compile(
    r"\b(?:originally\s+)?received\s*[:\-–—]\s*(?:on\s+)?$",
    re.IGNORECASE,
)

RE_DATE_RECEIVED = re.compile(
    r"\b(?:date\s+(?:of\s+)?received?|date\s+of\s+receipt)\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

RE_MANUSCRIPT_RECEIVED = re.compile(
    r"\b(?:manuscript|article|paper)\s+(?:originally\s+)?received\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

RE_REC_ABBR = re.compile(
    r"\brec(?:\.|\b)\s*[:\-–—]?\s*(?:on\s+)?$",
    re.IGNORECASE,
)

RE_SENTENCE_RECEIVED = re.compile(
    r"\b(?:this\s+)?(?:manuscript|article|paper)?\s*(?:was\s+)?(?:originally\s+)?received(?:\s+on)?\s*$",
    re.IGNORECASE,
)

RE_RECEIVED_ON = re.compile(
    r"\breceived\s+on\s*[:\-–—]?\s*$",
    re.IGNORECASE,
)

RE_GENERIC_RECEIVED = re.compile(
    r"\breceived\s*$",
    re.IGNORECASE,
)

# Following label pattern: e.g. 15 January 2025 (received)
RE_POST_RECEIVED = re.compile(
    r"^\s*[\(\[]\s*(?:date\s+)?received\s*[\)\]]",
    re.IGNORECASE,
)


def classify_candidate_context(
    pre_text: str,
    post_text: str,
) -> Tuple[str, str, str]:
    """
    Classifies the role of a date candidate based on preceding and following text.
    Returns: (role, label_pattern_name, matched_label_text)
    Roles: RECEIVED, REVISED, ACCEPTED, PUBLISHED, SUBMITTED, AMBIGUOUS, UNRELATED
    """
    # Look at the immediate tail of preceding text (up to 120 chars)
    # If there are clause boundaries like ';' or '\n' or '|' or '•', take after the last boundary
    cleaned_pre = pre_text
    for sep in [";", "\n", "\r", "|", "•"]:
        if sep in cleaned_pre:
            cleaned_pre = cleaned_pre.split(sep)[-1]

    # Also handle sentence delimiters like ". "
    if ". " in cleaned_pre:
        cleaned_pre = cleaned_pre.split(". ")[-1]

    # Clean and normalize whitespace (including tabs)
    trimmed_pre = re.sub(r"\s+", " ", cleaned_pre).strip()

    # 1. Check REVISED first (to prevent "received in revised form" matching "received")
    m = RE_ROLE_REVISED.search(trimmed_pre)
    if m:
        return "REVISED", "REVISED", m.group(0).strip()

    # 2. Check ACCEPTED
    m = RE_ROLE_ACCEPTED.search(trimmed_pre)
    if m:
        return "ACCEPTED", "ACCEPTED", m.group(0).strip()

    # 3. Check PUBLISHED
    m = RE_ROLE_PUBLISHED.search(trimmed_pre)
    if m:
        return "PUBLISHED", "PUBLISHED", m.group(0).strip()

    # 4. Check SUBMITTED
    m = RE_ROLE_SUBMITTED.search(trimmed_pre)
    if m:
        return "SUBMITTED", "SUBMITTED", m.group(0).strip()

    # 5. Check Explicit / Documented RECEIVED patterns (specific before generic)
    if RE_DATE_RECEIVED.search(trimmed_pre):
        return "RECEIVED", "DATE_RECEIVED", "Date received:"
    if RE_MANUSCRIPT_RECEIVED.search(trimmed_pre):
        return "RECEIVED", "MANUSCRIPT_RECEIVED", "Manuscript received:"
    if RE_EXPLICIT_RECEIVED.search(trimmed_pre):
        return "RECEIVED", "EXPLICIT_RECEIVED", "Received:"
    if RE_REC_ABBR.search(trimmed_pre):
        return "RECEIVED", "REC_ABBR", "Rec.:"
    if RE_SENTENCE_RECEIVED.search(trimmed_pre):
        return "RECEIVED", "SENTENCE_RECEIVED", "Manuscript was received on"
    if RE_RECEIVED_ON.search(trimmed_pre):
        return "RECEIVED", "RECEIVED_ON", "Received on"
    if RE_GENERIC_RECEIVED.search(trimmed_pre):
        return "RECEIVED", "EXPLICIT_RECEIVED", "Received"

    # 6. Check post-text for label (e.g. "15 Jan 2025 (received)")
    if RE_POST_RECEIVED.search(post_text):
        return "RECEIVED", "POST_RECEIVED", "(received)"

    # 7. Check AMBIGUOUS label (e.g. "Date: 15 January 2025")
    if RE_ROLE_AMBIGUOUS.search(trimmed_pre):
        return "AMBIGUOUS", "AMBIGUOUS_LABEL", "Date:"

    return "UNRELATED", "NONE", ""


def extract_candidates_from_blocks(blocks: List[TextBlock]) -> List[DateCandidate]:
    """
    Extracts and evaluates all candidate dates across all text blocks in the document.
    """
    candidates: List[DateCandidate] = []

    for block in blocks:
        text = block.text
        if not text:
            continue

        spans = find_date_spans_in_text(text)
        for start_idx, end_idx, matched_date in spans:
            pre_text = text[:start_idx]
            post_text = text[end_idx:]

            role, label_pat, label_text = classify_candidate_context(pre_text, post_text)

            parsed = parse_candidate_date_string(matched_date)

            score = compute_candidate_score(
                role=role,
                label_pattern=label_pat,
                format_type=parsed.format_type,
                is_calendar_valid=parsed.is_calendar_valid,
                is_ambiguous_numeric=parsed.is_ambiguous_numeric,
                source=block.source,
            )

            # Build surrounding evidence snippet
            snippet_start = max(0, start_idx - 40)
            snippet_end = min(len(text), end_idx + 40)
            evidence = text[snippet_start:snippet_end].replace("\n", " ").strip()

            candidate = DateCandidate(
                raw_text=matched_date,
                normalized_date=parsed.normalized_date,
                role=role,
                label_text=label_text,
                evidence=evidence,
                confidence_score=score,
                is_calendar_valid=parsed.is_calendar_valid,
                is_ambiguous_numeric=parsed.is_ambiguous_numeric,
                source=block.source,
            )
            candidates.append(candidate)

    return candidates


def resolve_received_date(
    filename: str,
    candidates: List[DateCandidate],
) -> ExtractionResult:
    """
    Deterministic conflict-resolution engine for candidate dates.
    Applies the assessment's documented rules to select the true received date.
    """
    received_candidates = [c for c in candidates if c.role == "RECEIVED"]
    competing_candidates = [c for c in candidates if c.role in ("REVISED", "ACCEPTED", "PUBLISHED", "SUBMITTED")]

    # 1. No received date candidates found
    if not received_candidates:
        if competing_candidates:
            roles = sorted(set(c.role for c in competing_candidates))
            return ExtractionResult(
                file=filename,
                received_date="invalid",
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                extraction_status=ExtractionStatus.NO_RECEIVED_DATE,
                reason=f"No received date found (only competing roles: {', '.join(roles)})",
            )
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.NO_RECEIVED_DATE,
            reason="No received date label found in document",
        )

    # 2. Check for invalid calendar dates labelled as received date
    # Requirement: "A malformed date labelled as the received date: return invalid rather than selecting an unrelated date."
    for c in received_candidates:
        if not c.is_calendar_valid:
            return ExtractionResult(
                file=filename,
                received_date="invalid",
                raw_date=c.raw_text,
                evidence=c.evidence,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                extraction_status=ExtractionStatus.INVALID_CALENDAR_DATE,
                reason=f"Invalid calendar date labelled as received: {c.raw_text}",
            )

    # 3. Check for ambiguous numeric dates labelled as received date
    # Requirement: "An ambiguous numeric date without an established convention: return invalid."
    for c in received_candidates:
        if c.is_ambiguous_numeric:
            return ExtractionResult(
                file=filename,
                received_date="invalid",
                raw_date=c.raw_text,
                evidence=c.evidence,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                extraction_status=ExtractionStatus.AMBIGUOUS_DATE,
                reason=f"Ambiguous numeric date without established convention: {c.raw_text}",
            )

    # 4. Check for conflicts among received candidates
    normalized_dates = [c.normalized_date for c in received_candidates if c.normalized_date]
    unique_dates = sorted(set(normalized_dates))

    if len(unique_dates) == 0:
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.NO_RECEIVED_DATE,
            reason="Received date candidates could not be parsed into valid dates",
        )

    if len(unique_dates) > 1:
        # Two or more different dates labelled as received date
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.CONFLICTING_DATES,
            reason=f"Conflicting received dates detected: {', '.join(unique_dates)}",
        )

    # Exactly one consistent received date across all mentions
    chosen_date = unique_dates[0]
    matching_candidates = [c for c in received_candidates if c.normalized_date == chosen_date]
    primary_candidate = matching_candidates[0]

    score, level, status, reason = score_extraction_result(matching_candidates, conflicting=False)

    return ExtractionResult(
        file=filename,
        received_date=chosen_date,
        raw_date=primary_candidate.raw_text,
        evidence=primary_candidate.evidence,
        confidence_score=score,
        confidence_level=level,
        extraction_status=status,
        reason=reason,
    )
