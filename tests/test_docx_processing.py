"""
Tests for DOCX file processing, tables, headers, footers, empty files, and corrupted documents.
"""

from pathlib import Path
import pytest
from manusure.core import extract_received_date, process_directory
from manusure.models import ExtractionStatus


class TestDocxProcessing:
    """Test DOCX extraction across structure types and resilience to corruption."""

    def test_normal_docx(self, create_docx):
        doc_path = create_docx("normal.docx", paragraphs=["Received: 15 January 2025"])
        res = extract_received_date(doc_path)
        assert res.received_date == "2025-01-15"

    def test_empty_docx(self, create_docx):
        doc_path = create_docx("empty.docx", paragraphs=[])
        res = extract_received_date(doc_path)
        assert res.received_date == "invalid"
        assert res.extraction_status == ExtractionStatus.NO_RECEIVED_DATE

    def test_table_cell_and_row_date(self, create_docx):
        table_data = [
            ["Status", "Date"],
            ["Received", "15 January 2025"],
            ["Revised", "20 February 2025"],
            ["Accepted", "10 March 2025"],
        ]
        doc_path = create_docx("table_doc.docx", tables_data=[table_data])
        res = extract_received_date(doc_path)
        assert res.received_date == "2025-01-15"

    def test_header_date(self, create_docx):
        doc_path = create_docx(
            "header_doc.docx",
            paragraphs=["Document Body Content Here"],
            header_text="Journal of Modern Science | Received: 15 January 2025",
        )
        res = extract_received_date(doc_path)
        assert res.received_date == "2025-01-15"

    def test_footer_date(self, create_docx):
        doc_path = create_docx(
            "footer_doc.docx",
            paragraphs=["Document Body Content Here"],
            footer_text="Manuscript received on 15 Jan 2025. All rights reserved.",
        )
        res = extract_received_date(doc_path)
        assert res.received_date == "2025-01-15"

    def test_corrupt_docx_returns_invalid(self, create_corrupt_docx):
        corrupt_path = create_corrupt_docx("corrupted.docx")
        res = extract_received_date(corrupt_path)
        assert res.received_date == "invalid"
        assert res.extraction_status == ExtractionStatus.CORRUPT_FILE

    def test_corrupt_file_does_not_halt_batch(self, tmp_path, create_docx, create_corrupt_docx):
        # Create a mix of valid and corrupted files
        doc1 = create_docx("doc1.docx", paragraphs=["Received: 10 January 2025"])
        doc2 = create_corrupt_docx("doc2.docx")
        doc3 = create_docx("doc3.docx", paragraphs=["Received: 25 January 2025"])

        results = process_directory(tmp_path)
        res_map = {r.file: r.received_date for r in results}

        assert res_map.get("doc1.docx") == "2025-01-10"
        assert res_map.get("doc2.docx") == "invalid"
        assert res_map.get("doc3.docx") == "2025-01-25"

    def test_temporary_files_are_ignored(self, tmp_path, create_docx):
        valid = create_docx("valid_paper.docx", paragraphs=["Received: 15 January 2025"])
        # Temporary Word lock file starting with ~$
        temp_file = tmp_path / "~$valid_paper.docx"
        temp_file.write_text("lock file content", encoding="utf-8")

        results = process_directory(tmp_path)
        filenames = [r.file for r in results]
        assert "valid_paper.docx" in filenames
        assert "~$valid_paper.docx" not in filenames
