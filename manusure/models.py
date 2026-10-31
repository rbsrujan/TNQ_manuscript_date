"""
Data models and enumerations for ManuSure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ConfidenceLevel(str, Enum):
    """Documented confidence tiers for extraction reliability."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ExtractionStatus(str, Enum):
    """Categorized status of the extraction attempt."""
    SUCCESS = "SUCCESS"
    NO_RECEIVED_DATE = "NO_RECEIVED_DATE"
    AMBIGUOUS_DATE = "AMBIGUOUS_DATE"
    INVALID_CALENDAR_DATE = "INVALID_CALENDAR_DATE"
    CONFLICTING_DATES = "CONFLICTING_DATES"
    PARSE_ERROR = "PARSE_ERROR"
    CORRUPT_FILE = "CORRUPT_FILE"


@dataclass
class DateCandidate:
    """Represents a date candidate discovered in the document with its context and role."""
    raw_text: str
    normalized_date: Optional[str]
    role: str
    label_text: str
    evidence: str
    confidence_score: float = 0.0
    is_calendar_valid: bool = True
    is_ambiguous_numeric: bool = False
    source: str = "paragraph"


@dataclass
class ExtractionResult:
    """
    Internal structured result for diagnostics, confidence scoring, and verification.
    Only `file` and `received_date` are written to the public CSV output.
    """
    file: str
    received_date: str
    raw_date: Optional[str] = None
    evidence: Optional[str] = None
    confidence_score: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    extraction_status: ExtractionStatus = ExtractionStatus.NO_RECEIVED_DATE
    reason: str = ""
