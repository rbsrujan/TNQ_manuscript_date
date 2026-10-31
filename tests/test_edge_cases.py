"""
Tests for edge cases: conflicting dates, identical dates, confidence scoring, and malformed inputs.
"""

import pytest
from manusure.core import extract_received_date
from manusure.models import ConfidenceLevel, ExtractionStatus


class TestEdgeCases:
    """Test edge cases, conflicting dates, and confidence scoring."""

    def test_conflicting_received_dates(self, create_docx):
        p = [
            "Received: 15 January 2025",
            "Later note: Received: 20 February 2025",
        ]
        doc_path = create_docx("conflicting.docx", paragraphs=p)
        res = extract_received_date(doc_path)
        assert res.received_date == "invalid"
        assert res.extraction_status == ExtractionStatus.CONFLICTING_DATES
        assert res.confidence_score == 0.0
        assert res.confidence_level == ConfidenceLevel.LOW

    def test_multiple_identical_received_dates(self, create_docx):
        p = [
            "Received: 15 January 2025",
            "Reiterated in footer note: Received: 15 January 2025",
        ]
        doc_path = create_docx("identical.docx", paragraphs=p)
        res = extract_received_date(doc_path)
        assert res.received_date == "2025-01-15"
        assert res.extraction_status == ExtractionStatus.SUCCESS
        assert res.confidence_score >= 0.85
        assert res.confidence_level == ConfidenceLevel.HIGH

    def test_malformed_calendar_date_labelled_received(self, create_docx):
        # Assessment: "A malformed date labelled as the received date: return invalid rather than selecting an unrelated date."
        p = [
            "Received: 35 January 2025",
            "Published: 10 March 2025",
        ]
        doc_path = create_docx("malformed_cal.docx", paragraphs=p)
        res = extract_received_date(doc_path)
        assert res.received_date == "invalid"
        assert res.extraction_status == ExtractionStatus.INVALID_CALENDAR_DATE

    def test_ambiguous_numeric_date_labelled_received(self, create_docx):
        # Assessment: "Received: 01/02/2025 -> Expected behavior: return invalid if numeric date is ambiguous"
        p = [
            "Received: 01/02/2025",
        ]
        doc_path = create_docx("ambiguous_num.docx", paragraphs=p)
        res = extract_received_date(doc_path)
        assert res.received_date == "invalid"
        assert res.extraction_status == ExtractionStatus.AMBIGUOUS_DATE

    def test_unusual_whitespace_and_punctuation(self, create_docx):
        p = [
            "   RECEIVED   :   \t  15   January   2025   \n",
        ]
        doc_path = create_docx("whitespace.docx", paragraphs=p)
        res = extract_received_date(doc_path)
        assert res.received_date == "2025-01-15"
        assert res.confidence_level == ConfidenceLevel.HIGH

    def test_confidence_scoring_relative_strengths(self, create_docx):
        # Direct explicit label vs weak/narrative label
        doc_explicit = create_docx("explicit.docx", paragraphs=["Received: 15 January 2025"])
        res_explicit = extract_received_date(doc_explicit)

        doc_narrative = create_docx("narrative2.docx", paragraphs=["This manuscript was received on 15 Jan 2025."])
        res_narrative = extract_received_date(doc_narrative)

        assert res_explicit.confidence_score >= res_narrative.confidence_score
        assert res_explicit.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
        assert res_narrative.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
