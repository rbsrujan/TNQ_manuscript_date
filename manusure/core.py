"""
Core extraction pipeline and batch processor for ManuSure.
"""

import csv
from pathlib import Path
from typing import List, Optional, Union

from .docx_reader import CorruptDocxError, extract_text_blocks_from_docx
from .models import ConfidenceLevel, ExtractionResult, ExtractionStatus
from .nlp_extractor import extract_candidates_from_blocks, resolve_received_date


def extract_received_date(docx_path: Union[str, Path]) -> ExtractionResult:
    """
    Extracts the received date from a single DOCX manuscript file.
    Returns an ExtractionResult.
    """
    path = Path(docx_path)
    filename = path.name

    if not path.is_file():
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.CORRUPT_FILE,
            reason=f"File does not exist: {path}",
        )

    try:
        blocks = extract_text_blocks_from_docx(path)
    except CorruptDocxError as exc:
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.CORRUPT_FILE,
            reason=str(exc),
        )
    except Exception as exc:
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.CORRUPT_FILE,
            reason=f"Unexpected error processing document: {exc}",
        )

    if not blocks:
        return ExtractionResult(
            file=filename,
            received_date="invalid",
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            extraction_status=ExtractionStatus.NO_RECEIVED_DATE,
            reason="Document is empty or contains no extractable text",
        )

    candidates = extract_candidates_from_blocks(blocks)
    result = resolve_received_date(filename, candidates)
    return result


def process_directory(
    input_dir: Union[str, Path],
    output_csv: Optional[Union[str, Path]] = None,
) -> List[ExtractionResult]:
    """
    Processes all eligible DOCX files directly inside input_dir in deterministic alphabetical order.
    Optionally writes the results to output_csv with the required schema: `file,received_date`.
    """
    dir_path = Path(input_dir)
    if not dir_path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {dir_path}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {dir_path}")

    # Process only .docx files directly in the directory (non-recursive)
    # Ignore temporary files starting with ~$
    docx_files = [
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() == ".docx" and not f.name.startswith("~$")
    ]

    # Deterministic alphabetical ordering
    docx_files.sort(key=lambda p: p.name)

    results: List[ExtractionResult] = []
    for f in docx_files:
        res = extract_received_date(f)
        results.append(res)

    if output_csv is not None:
        csv_path = Path(output_csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, mode="w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(["file", "received_date"])
            for r in results:
                writer.writerow([r.file, r.received_date])

    return results
