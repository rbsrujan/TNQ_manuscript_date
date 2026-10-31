"""
Pytest configuration and fixtures for ManuSure test suite.
Programmatically creates sample DOCX test files.
"""

from pathlib import Path
from typing import Callable, Optional
import docx
import pytest


@pytest.fixture
def create_docx(tmp_path: Path) -> Callable[..., Path]:
    """
    Factory fixture to create a valid .docx file with custom paragraphs, tables, headers, and footers.
    """
    def _create(
        filename: str,
        paragraphs: Optional[list] = None,
        tables_data: Optional[list] = None,
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> Path:
        doc = docx.Document()
        filepath = tmp_path / filename

        if header_text:
            section = doc.sections[0]
            section.header.paragraphs[0].text = header_text

        if footer_text:
            section = doc.sections[0]
            section.footer.paragraphs[0].text = footer_text

        if paragraphs:
            for p in paragraphs:
                doc.add_paragraph(p)

        if tables_data:
            for table_rows in tables_data:
                num_rows = len(table_rows)
                num_cols = len(table_rows[0]) if num_rows > 0 else 1
                table = doc.add_table(rows=num_rows, cols=num_cols)
                for r_idx, row_values in enumerate(table_rows):
                    for c_idx, val in enumerate(row_values):
                        table.cell(r_idx, c_idx).text = str(val)

        doc.save(str(filepath))
        return filepath

    return _create


@pytest.fixture
def create_corrupt_docx(tmp_path: Path) -> Callable[[str], Path]:
    """
    Factory fixture to create an unreadable / corrupted .docx file.
    """
    def _create(filename: str) -> Path:
        filepath = tmp_path / filename
        # Write random corrupted binary content that is not a valid zip archive
        filepath.write_bytes(b"\x00\x01\x02\x03\x04CORRUPTED_WORD_DOCUMENT_PAYLOAD\xff\xfe")
        return filepath

    return _create
