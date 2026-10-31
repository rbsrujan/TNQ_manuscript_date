"""
Tests for semantic role classification, competing dates, and context resolution.
"""

import pytest
from pathlib import Path
from manusure.core import extract_received_date
from manusure.docx_reader import TextBlock
from manusure.nlp_extractor import (
    classify_candidate_context,
    extract_candidates_from_blocks,
    resolve_received_date,
)


class TestSemanticClassification:
    """Test contextual classification of date roles."""

    def test_explicit_received_label(self):
        role, pat, _ = classify_candidate_context("Received: ", "")
        assert role == "RECEIVED"
        assert pat == "EXPLICIT_RECEIVED"

    def test_date_received_label(self):
        role, pat, _ = classify_candidate_context("Date received: ", "")
        assert role == "RECEIVED"
        assert pat == "DATE_RECEIVED"

    def test_manuscript_received_label(self):
        role, pat, _ = classify_candidate_context("Manuscript received: ", "")
        assert role == "RECEIVED"
        assert pat == "MANUSCRIPT_RECEIVED"

    def test_sentence_received_label(self):
        role, pat, _ = classify_candidate_context("This manuscript was received on ", "")
        assert role == "RECEIVED"
        assert pat == "SENTENCE_RECEIVED"

    def test_rec_abbreviation_label(self):
        role, pat, _ = classify_candidate_context("Rec.: ", "")
        assert role == "RECEIVED"
        assert pat == "REC_ABBR"

    def test_post_received_label(self):
        role, pat, _ = classify_candidate_context("", " (received)")
        assert role == "RECEIVED"
        assert pat == "POST_RECEIVED"

    def test_competing_revised_label(self):
        role, pat, _ = classify_candidate_context("Revised: ", "")
        assert role == "REVISED"

    def test_competing_received_in_revised_form(self):
        # Must NOT be classified as RECEIVED
        role, pat, _ = classify_candidate_context("Received in revised form: ", "")
        assert role == "REVISED"

    def test_competing_accepted_label(self):
        role, pat, _ = classify_candidate_context("Accepted: ", "")
        assert role == "ACCEPTED"

    def test_competing_published_label(self):
        role, pat, _ = classify_candidate_context("Published online: ", "")
        assert role == "PUBLISHED"

    def test_competing_submitted_label(self):
        role, pat, _ = classify_candidate_context("Submitted: ", "")
        assert role == "SUBMITTED"

    def test_ambiguous_date_label(self):
        # Assessment: "Date: 15 January 2025 -> do not automatically assume this is the received date"
        role, pat, _ = classify_candidate_context("Date: ", "")
        assert role == "AMBIGUOUS"

    def test_unrelated_text(self):
        role, pat, _ = classify_candidate_context("The experiment took place on ", "")
        assert role == "UNRELATED"


class TestDocumentExtractionScenarios:
    """Test full document-level candidate resolution scenarios."""

    def test_received_and_revised_and_accepted(self, create_docx):
        p = [
            "Manuscript Title: Advances in NLP",
            "Received: 15 January 2025; Revised: 20 February 2025; Accepted: 10 March 2025",
        ]
        doc_path = create_docx("multi_role.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "2025-01-15"
        assert result.confidence_level.value == "High"

    def test_only_revised_date_returns_invalid(self, create_docx):
        p = [
            "Manuscript Title: Quantum Studies",
            "Revised: 20 February 2025; Accepted: 10 March 2025",
        ]
        doc_path = create_docx("only_revised.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "invalid"

    def test_only_accepted_date_returns_invalid(self, create_docx):
        p = [
            "Manuscript Title: BioTech Notes",
            "Accepted: 10 March 2025",
        ]
        doc_path = create_docx("only_accepted.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "invalid"

    def test_only_published_date_returns_invalid(self, create_docx):
        p = [
            "Manuscript Title: Astronomical Discoveries",
            "Published online: 15 April 2025",
        ]
        doc_path = create_docx("only_published.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "invalid"

    def test_only_submitted_date_returns_invalid(self, create_docx):
        p = [
            "Manuscript Title: Geological Survey",
            "Submitted: 05 January 2025",
        ]
        doc_path = create_docx("only_submitted.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "invalid"

    def test_ambiguous_date_label_returns_invalid(self, create_docx):
        p = [
            "Manuscript Title: Materials Science",
            "Date: 15 January 2025",
        ]
        doc_path = create_docx("ambiguous_label.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "invalid"

    def test_unrelated_dates_return_invalid(self, create_docx):
        p = [
            "Introduction",
            "According to Smith et al. (2020), the data collected on 14 March 2019 showed significant variation.",
        ]
        doc_path = create_docx("unrelated_text.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "invalid"

    def test_narrative_sentence_received(self, create_docx):
        p = [
            "This manuscript was received on January 15, 2025 and accepted for publication on March 1, 2025.",
        ]
        doc_path = create_docx("narrative.docx", paragraphs=p)
        result = extract_received_date(doc_path)
        assert result.received_date == "2025-01-15"
