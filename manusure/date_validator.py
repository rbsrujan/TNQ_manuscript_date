"""
Date parsing, normalization, and calendar validation for ManuSure.
"""

import datetime
import re
from typing import Dict, List, Optional, Tuple

MONTH_MAP: Dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Regex for matching date candidates in running text
# 1. Day Month Year: e.g. 15 January 2025, 15 Jan 2025, 15th January 2025, 15-Jan-2025
RE_DMY = re.compile(
    r"\b([0-3]?\d)(?:st|nd|rd|th)?[\s\-]+([A-Za-z]+)\.?[\s\-]+([12]\d{3})\b",
    re.IGNORECASE,
)

# 2. Month Day Year: e.g. January 15, 2025, Jan 15, 2025, Jan. 15, 2025, January 15th, 2025
RE_MDY = re.compile(
    r"\b([A-Za-z]+)\.?[\s\-]+([0-3]?\d)(?:st|nd|rd|th)?(?:,)?[\s\-]+([12]\d{3})\b",
    re.IGNORECASE,
)

# 3. ISO format: e.g. 2025-01-15, 2025/01/15, 2025.01.15
RE_ISO = re.compile(
    r"\b([12]\d{3})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b"
)

# 4. Pure numeric: e.g. 15/01/2025, 01/02/2025, 15-01-2025, 15.01.2025
RE_NUMERIC = re.compile(
    r"\b([0-3]?\d)[-/.]([0-3]?\d)[-/.]([12]\d{3})\b"
)


class ParsedDateResult:
    """Detailed outcome of a date parse attempt."""
    def __init__(
        self,
        raw_text: str,
        normalized_date: Optional[str] = None,
        is_calendar_valid: bool = False,
        is_ambiguous_numeric: bool = False,
        format_type: str = "UNKNOWN",
        error_message: str = "",
    ):
        self.raw_text = raw_text
        self.normalized_date = normalized_date
        self.is_calendar_valid = is_calendar_valid
        self.is_ambiguous_numeric = is_ambiguous_numeric
        self.format_type = format_type
        self.error_message = error_message

    @property
    def is_usable(self) -> bool:
        return (
            self.is_calendar_valid
            and not self.is_ambiguous_numeric
            and self.normalized_date is not None
        )


def _validate_calendar_date(year: int, month: int, day: int) -> Optional[datetime.date]:
    """Validates year, month, day bounds and leap year correctness."""
    if not (1900 <= year <= 2099):
        return None
    try:
        return datetime.date(year, month, day)
    except (ValueError, OverflowError):
        return None


def parse_candidate_date_string(date_str: str) -> ParsedDateResult:
    """
    Parses a date string, checks calendar validity, leap years, and flags ambiguous numeric dates.
    Returns ParsedDateResult.
    """
    cleaned = date_str.strip()

    # 1. Check ISO format (YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD)
    m_iso = re.match(r"^([12]\d{3})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])$", cleaned)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        dt = _validate_calendar_date(y, m, d)
        if dt:
            return ParsedDateResult(
                raw_text=cleaned,
                normalized_date=dt.isoformat(),
                is_calendar_valid=True,
                format_type="ISO",
            )
        else:
            return ParsedDateResult(
                raw_text=cleaned,
                is_calendar_valid=False,
                format_type="ISO",
                error_message=f"Invalid calendar date: {y}-{m}-{d}",
            )

    # 2. Check Day Month Year: e.g. 15 January 2025, 15-Jan-2025
    m_dmy = re.match(r"^([0-3]?\d)(?:st|nd|rd|th)?[\s\-]+([A-Za-z]+)\.?[\s\-]+([12]\d{3})$", cleaned, re.IGNORECASE)
    if m_dmy:
        d_str, month_str, y_str = m_dmy.group(1), m_dmy.group(2).lower(), m_dmy.group(3)
        month = MONTH_MAP.get(month_str)
        if not month:
            return ParsedDateResult(
                raw_text=cleaned,
                is_calendar_valid=False,
                format_type="DMY",
                error_message=f"Unrecognized month name: {month_str}",
            )
        d, y = int(d_str), int(y_str)
        dt = _validate_calendar_date(y, month, d)
        if dt:
            fmt = "TEXT_FULL" if len(month_str) > 3 else "TEXT_ABBR"
            return ParsedDateResult(
                raw_text=cleaned,
                normalized_date=dt.isoformat(),
                is_calendar_valid=True,
                format_type=fmt,
            )
        else:
            return ParsedDateResult(
                raw_text=cleaned,
                is_calendar_valid=False,
                format_type="DMY",
                error_message=f"Invalid calendar date: {y}-{month}-{d}",
            )

    # 3. Check Month Day Year: e.g. January 15, 2025, Jan 15 2025
    m_mdy = re.match(r"^([A-Za-z]+)\.?[\s\-]+([0-3]?\d)(?:st|nd|rd|th)?(?:,)?[\s\-]+([12]\d{3})$", cleaned, re.IGNORECASE)
    if m_mdy:
        month_str, d_str, y_str = m_mdy.group(1).lower(), m_mdy.group(2), m_mdy.group(3)
        month = MONTH_MAP.get(month_str)
        if not month:
            return ParsedDateResult(
                raw_text=cleaned,
                is_calendar_valid=False,
                format_type="MDY",
                error_message=f"Unrecognized month name: {month_str}",
            )
        d, y = int(d_str), int(y_str)
        dt = _validate_calendar_date(y, month, d)
        if dt:
            fmt = "TEXT_FULL" if len(month_str) > 3 else "TEXT_ABBR"
            return ParsedDateResult(
                raw_text=cleaned,
                normalized_date=dt.isoformat(),
                is_calendar_valid=True,
                format_type=fmt,
            )
        else:
            return ParsedDateResult(
                raw_text=cleaned,
                is_calendar_valid=False,
                format_type="MDY",
                error_message=f"Invalid calendar date: {y}-{month}-{d}",
            )

    # 4. Check Pure Numeric: e.g. 15/01/2025, 01/02/2025
    m_num = re.match(r"^([0-3]?\d)[-/.]([0-3]?\d)[-/.]([12]\d{3})$", cleaned)
    if m_num:
        n1, n2, y = int(m_num.group(1)), int(m_num.group(2)), int(m_num.group(3))

        # Check calendar plausibility first
        # Case A: n1 > 12 and n2 <= 12 -> Unambiguous DD/MM/YYYY
        if n1 > 12 and 1 <= n2 <= 12:
            dt = _validate_calendar_date(y, n2, n1)
            if dt:
                return ParsedDateResult(
                    raw_text=cleaned,
                    normalized_date=dt.isoformat(),
                    is_calendar_valid=True,
                    format_type="NUMERIC_UNAMBIGUOUS",
                )
            else:
                return ParsedDateResult(
                    raw_text=cleaned,
                    is_calendar_valid=False,
                    format_type="NUMERIC_INVALID",
                    error_message=f"Invalid calendar day: {n1} in month {n2}",
                )

        # Case B: n2 > 12 and n1 <= 12 -> Unambiguous MM/DD/YYYY
        if n2 > 12 and 1 <= n1 <= 12:
            dt = _validate_calendar_date(y, n1, n2)
            if dt:
                return ParsedDateResult(
                    raw_text=cleaned,
                    normalized_date=dt.isoformat(),
                    is_calendar_valid=True,
                    format_type="NUMERIC_UNAMBIGUOUS",
                )
            else:
                return ParsedDateResult(
                    raw_text=cleaned,
                    is_calendar_valid=False,
                    format_type="NUMERIC_INVALID",
                    error_message=f"Invalid calendar day: {n2} in month {n1}",
                )

        # Case C: Both n1 <= 12 and n2 <= 12
        if 1 <= n1 <= 12 and 1 <= n2 <= 12:
            if n1 == n2:
                # e.g. 05/05/2025 -> Unambiguous: 5th of May
                dt = _validate_calendar_date(y, n1, n2)
                return ParsedDateResult(
                    raw_text=cleaned,
                    normalized_date=dt.isoformat() if dt else None,
                    is_calendar_valid=dt is not None,
                    format_type="NUMERIC_UNAMBIGUOUS",
                )
            else:
                # e.g. 01/02/2025 -> Ambiguous (could be 1 Feb or 2 Jan)
                # Requirement: Ambiguous numeric date without an established convention: return invalid.
                return ParsedDateResult(
                    raw_text=cleaned,
                    is_calendar_valid=True,
                    is_ambiguous_numeric=True,
                    format_type="NUMERIC_AMBIGUOUS",
                    error_message=f"Ambiguous numeric date without convention: {cleaned}",
                )

        # Invalid numeric components
        return ParsedDateResult(
            raw_text=cleaned,
            is_calendar_valid=False,
            format_type="NUMERIC_INVALID",
            error_message=f"Numeric values out of range: {n1}/{n2}/{y}",
        )

    # Could not match any date pattern
    return ParsedDateResult(
        raw_text=cleaned,
        is_calendar_valid=False,
        format_type="UNKNOWN",
        error_message="Format not recognized as a valid date structure",
    )


def find_date_spans_in_text(text: str) -> List[Tuple[int, int, str]]:
    """
    Scans running text and finds all candidate date spans (start_idx, end_idx, matched_text).
    Avoids duplicate or overlapping spans.
    """
    spans: List[Tuple[int, int, str]] = []
    occupied: List[Tuple[int, int]] = []

    def _is_overlapping(s: int, e: int) -> bool:
        for os, oe in occupied:
            if max(s, os) < min(e, oe):
                return True
        return False

    # Check ISO first (e.g. 2025-01-15)
    for m in RE_ISO.finditer(text):
        s, e = m.span()
        if not _is_overlapping(s, e):
            spans.append((s, e, m.group(0)))
            occupied.append((s, e))

    # Check DMY (e.g. 15 January 2025, 15 Jan 2025)
    for m in RE_DMY.finditer(text):
        s, e = m.span()
        if not _is_overlapping(s, e):
            # Verify the word looks like a month or month-like word
            word = m.group(2).lower()
            if word in MONTH_MAP or len(word) >= 3:
                spans.append((s, e, m.group(0)))
                occupied.append((s, e))

    # Check MDY (e.g. January 15, 2025)
    for m in RE_MDY.finditer(text):
        s, e = m.span()
        if not _is_overlapping(s, e):
            word = m.group(1).lower()
            if word in MONTH_MAP or len(word) >= 3:
                spans.append((s, e, m.group(0)))
                occupied.append((s, e))

    # Check numeric dates (e.g. 15/01/2025, 01/02/2025)
    for m in RE_NUMERIC.finditer(text):
        s, e = m.span()
        if not _is_overlapping(s, e):
            spans.append((s, e, m.group(0)))
            occupied.append((s, e))

    # Sort spans by position in text
    spans.sort(key=lambda x: x[0])
    return spans
