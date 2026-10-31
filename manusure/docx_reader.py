"""
DOCX reader and text block extractor for ManuSure.
Safely extracts paragraphs, tables, table rows, headers, and footers from .docx files.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import docx
from docx.opc.exceptions import OpcError, PackageNotFoundError
import zipfile


@dataclass
class TextBlock:
    text: str
    source: str  # "paragraph", "table_row", "table_cell", "header", "footer"


class CorruptDocxError(Exception):
    """Raised when a DOCX file cannot be read or parsed by python-docx."""
    pass


def extract_text_blocks_from_docx(file_path: Path) -> List[TextBlock]:
    """
    Safely reads a DOCX file and extracts text blocks from:
    1. Document paragraphs
    2. Tables (both individual cells and concatenated row texts)
    3. Headers and footers of all sections
    Raises CorruptDocxError if the document is unreadable or malformed.
    """
    blocks: List[TextBlock] = []

    try:
        doc = docx.Document(str(file_path))
    except (OpcError, PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError, Exception) as exc:
        raise CorruptDocxError(f"Failed to open DOCX file '{file_path.name}': {exc}") from exc

    # 1. Document Paragraphs
    try:
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                blocks.append(TextBlock(text=txt, source="paragraph"))
    except Exception as exc:
        raise CorruptDocxError(f"Failed to read paragraphs from '{file_path.name}': {exc}") from exc

    # 2. Document Tables
    try:
        for table in doc.tables:
            for row in table.rows:
                cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if not cell_texts:
                    continue

                # Concatenate row cells to preserve column associations
                # e.g. "Received" | "15 January 2025" -> "Received: 15 January 2025"
                if len(cell_texts) >= 2:
                    row_repr = f"{cell_texts[0]}: {' '.join(cell_texts[1:])}"
                    blocks.append(TextBlock(text=row_repr, source="table_row"))
                    # Also pipe-separated representation
                    pipe_repr = " | ".join(cell_texts)
                    if pipe_repr != row_repr:
                        blocks.append(TextBlock(text=pipe_repr, source="table_row"))

                # Also inspect each individual cell
                for cell in row.cells:
                    c_txt = cell.text.strip()
                    if c_txt:
                        blocks.append(TextBlock(text=c_txt, source="table_cell"))
    except Exception as exc:
        raise CorruptDocxError(f"Failed to read tables from '{file_path.name}': {exc}") from exc

    # 3. Document Headers and Footers
    try:
        for section in doc.sections:
            # Header
            try:
                if section.header:
                    for hp in section.header.paragraphs:
                        htxt = hp.text.strip()
                        if htxt:
                            blocks.append(TextBlock(text=htxt, source="header"))
                    for ht in section.header.tables:
                        for hr in ht.rows:
                            h_cells = [c.text.strip() for c in hr.cells if c.text.strip()]
                            if len(h_cells) >= 2:
                                blocks.append(TextBlock(text=f"{h_cells[0]}: {' '.join(h_cells[1:])}", source="header"))
                            for c in hr.cells:
                                if c.text.strip():
                                    blocks.append(TextBlock(text=c.text.strip(), source="header"))
            except Exception:
                pass  # Ignore uninitialized or linked header errors

            # Footer
            try:
                if section.footer:
                    for fp in section.footer.paragraphs:
                        ftxt = fp.text.strip()
                        if ftxt:
                            blocks.append(TextBlock(text=ftxt, source="footer"))
                    for ft in section.footer.tables:
                        for fr in ft.rows:
                            f_cells = [c.text.strip() for c in fr.cells if c.text.strip()]
                            if len(f_cells) >= 2:
                                blocks.append(TextBlock(text=f"{f_cells[0]}: {' '.join(f_cells[1:])}", source="footer"))
                            for c in fr.cells:
                                if c.text.strip():
                                    blocks.append(TextBlock(text=c.text.strip(), source="footer"))
            except Exception:
                pass  # Ignore uninitialized or linked footer errors
    except Exception:
        pass

    return blocks
