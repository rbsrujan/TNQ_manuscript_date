#!/usr/bin/env python3
"""
Test report generator for ManuSure.
Executes the automated checks independently, records expected vs actual outputs,
and writes test_report.csv with columns: checks,input,expected,actual,result.
"""

import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

import docx

from manusure.core import extract_received_date, process_directory
from manusure.date_validator import parse_candidate_date_string
from manusure.docx_reader import TextBlock
from manusure.nlp_extractor import (
    classify_candidate_context,
    extract_candidates_from_blocks,
    resolve_received_date,
)


def run_check(
    checks: str,
    input_desc: str,
    expected: str,
    actual: str,
) -> Tuple[str, str, str, str, str]:
    """Helper to evaluate check result."""
    result = "PASS" if actual == expected else "FAIL"
    return (checks, input_desc, expected, actual, result)


def generate_report(output_csv_path: Path) -> List[Tuple[str, str, str, str, str]]:
    """Runs all checks across all categories and returns the result records."""
    records: List[Tuple[str, str, str, str, str]] = []

    # Temporary directory for document fixtures
    temp_dir = Path(tempfile.mkdtemp(prefix="manusure_report_"))

    try:
        # =========================================================================
        # 1. Date Format and Calendar Validation Checks
        # =========================================================================
        date_cases = [
            ("Explicit received date (Full month)", "Received: 15 January 2025", "2025-01-15"),
            ("Abbreviated month received date", "Received: 15 Jan 2025", "2025-01-15"),
            ("Month Day Year format", "Received: January 15, 2025", "2025-01-15"),
            ("Month Day Year abbreviated", "Received: Jan 15, 2025", "2025-01-15"),
            ("Month Day Year with period", "Received: Jan. 15, 2025", "2025-01-15"),
            ("ISO received date (hyphens)", "Received: 2025-01-15", "2025-01-15"),
            ("ISO received date (slashes)", "Received: 2025/01/15", "2025-01-15"),
            ("ISO received date (dots)", "Received: 2025.01.15", "2025-01-15"),
            ("Numeric unambiguous DD/MM/YYYY (Day > 12)", "Received: 15/01/2025", "2025-01-15"),
            ("Numeric unambiguous DD-MM-YYYY (Day > 12)", "Received: 25-12-2024", "2024-12-25"),
            ("Numeric unambiguous identical day and month", "Received: 05/05/2025", "2025-05-05"),
            ("Ambiguous numeric date (01/02/2025)", "Received: 01/02/2025", "invalid"),
            ("Ambiguous numeric date (04/10/2024)", "Received: 04/10/2024", "invalid"),
            ("Ordinal suffix (15th January 2025)", "Received: 15th January 2025", "2025-01-15"),
            ("Ordinal suffix (1st February 2025)", "Received: 1st February 2025", "2025-02-01"),
            ("Ordinal suffix (2nd March 2024)", "Received: 2nd March 2024", "2024-03-02"),
            ("Ordinal suffix (3rd April 2025)", "Received: 3rd April 2025", "2025-04-03"),
            ("Hyphenated DMY format", "Received: 15-Jan-2025", "2025-01-15"),
            ("Invalid calendar date (Day 35)", "Received: 35 January 2025", "invalid"),
            ("Invalid calendar date (31 April)", "Received: 31 April 2025", "invalid"),
            ("Leap year valid date (29 Feb 2024)", "Received: 29 February 2024", "2024-02-29"),
            ("Non-leap year date (29 Feb 2023)", "Received: 29 February 2023", "invalid"),
            ("Century leap year (29 Feb 2000)", "Received: 29 February 2000", "2000-02-29"),
            ("Non-leap century (29 Feb 1900)", "Received: 29 February 1900", "invalid"),
            ("Unrecognized month name", "Received: 15 UnknownMonth 2025", "invalid"),
            ("Missing year in date", "Received: 15 January", "invalid"),
            ("Uppercase month text", "Received: 15 JANUARY 2025", "2025-01-15"),
            ("Lowercase month text", "Received: 15 january 2025", "2025-01-15"),
            ("Whitespace around date elements", "Received:   15   January   2025  ", "2025-01-15"),
        ]

        for check_name, text_input, expected_date in date_cases:
            # Create a docx file for this check
            fn = f"chk_date_{len(records)}.docx"
            fpath = temp_dir / fn
            doc = docx.Document()
            doc.add_paragraph(text_input)
            doc.save(str(fpath))

            actual_date = extract_received_date(fpath).received_date
            records.append(run_check(check_name, text_input, expected_date, actual_date))

        # =========================================================================
        # 2. Semantic Role Classification and Label Variations
        # =========================================================================
        semantic_cases = [
            ("Date received label", "Date received: 15 Jan 2025", "2025-01-15"),
            ("Manuscript received label", "Manuscript received: 15 January 2025", "2025-01-15"),
            ("Received on label", "Received on 15 January 2025", "2025-01-15"),
            ("Date of receipt label", "Date of receipt: 15 January 2025", "2025-01-15"),
            ("Abbreviated Rec. label", "Rec.: 15 Jan 2025", "2025-01-15"),
            ("Narrative sentence received", "This manuscript was received on 15 January 2025.", "2025-01-15"),
            ("Trailing received label", "15 January 2025 (received)", "2025-01-15"),
            ("Revised date only (No received)", "Revised: 20 February 2025", "invalid"),
            ("Accepted date only (No received)", "Accepted: 10 March 2025", "invalid"),
            ("Published online only (No received)", "Published online: 01 April 2025", "invalid"),
            ("Submitted date only (No received)", "Submitted: 05 January 2025", "invalid"),
            ("Received in revised form only", "Received in revised form: 20 February 2025", "invalid"),
            ("Ambiguous 'Date:' label", "Date: 15 January 2025", "invalid"),
            ("Unrelated citation date", "Smith et al. (2020) on 14 March 2019", "invalid"),
            ("Multiple roles in single document", "Received: 15 Jan 2025; Revised: 20 Feb 2025; Accepted: 10 Mar 2025", "2025-01-15"),
        ]

        for check_name, text_input, expected_date in semantic_cases:
            fn = f"chk_sem_{len(records)}.docx"
            fpath = temp_dir / fn
            doc = docx.Document()
            doc.add_paragraph(text_input)
            doc.save(str(fpath))

            actual_date = extract_received_date(fpath).received_date
            records.append(run_check(check_name, text_input, expected_date, actual_date))

        # =========================================================================
        # 3. Conflict Resolution and Multi-Candidate Mentions
        # =========================================================================
        # Case A: Two conflicting received dates
        f_conflict = temp_dir / "conflict.docx"
        doc = docx.Document()
        doc.add_paragraph("Received: 15 January 2025")
        doc.add_paragraph("Later note: Received: 20 February 2025")
        doc.save(str(f_conflict))
        actual = extract_received_date(f_conflict).received_date
        records.append(run_check(
            "Conflicting received dates",
            "Received: 15 January 2025 vs Received: 20 February 2025",
            "invalid",
            actual,
        ))

        # Case B: Multiple identical received dates
        f_identical = temp_dir / "identical.docx"
        doc = docx.Document()
        doc.add_paragraph("Received: 15 January 2025")
        doc.add_paragraph("Reiterated in footer note: Received: 15 January 2025")
        doc.save(str(f_identical))
        actual = extract_received_date(f_identical).received_date
        records.append(run_check(
            "Identical received date mentions",
            "Received: 15 January 2025 repeated twice",
            "2025-01-15",
            actual,
        ))

        # Case C: Malformed received date with valid revised date
        f_malformed_with_rev = temp_dir / "malformed_with_rev.docx"
        doc = docx.Document()
        doc.add_paragraph("Received: 35 January 2025; Revised: 20 February 2025")
        doc.save(str(f_malformed_with_rev))
        actual = extract_received_date(f_malformed_with_rev).received_date
        records.append(run_check(
            "Malformed received date with valid revised date",
            "Received: 35 January 2025; Revised: 20 February 2025",
            "invalid",
            actual,
        ))

        # =========================================================================
        # 4. DOCX Structural Processing and Resilience
        # =========================================================================
        # Empty DOCX
        f_empty = temp_dir / "empty.docx"
        doc = docx.Document()
        doc.save(str(f_empty))
        actual = extract_received_date(f_empty).received_date
        records.append(run_check("Empty DOCX document", "Empty document without paragraphs", "invalid", actual))

        # Table-based received date
        f_table = temp_dir / "table.docx"
        doc = docx.Document()
        tbl = doc.add_table(rows=2, cols=2)
        tbl.cell(0, 0).text = "Received"
        tbl.cell(0, 1).text = "15 January 2025"
        tbl.cell(1, 0).text = "Accepted"
        tbl.cell(1, 1).text = "20 February 2025"
        doc.save(str(f_table))
        actual = extract_received_date(f_table).received_date
        records.append(run_check("Received date in document table", "Table cell [Received | 15 January 2025]", "2025-01-15", actual))

        # Header-based received date
        f_header = temp_dir / "header.docx"
        doc = docx.Document()
        doc.sections[0].header.paragraphs[0].text = "Header text: Received: 15 January 2025"
        doc.add_paragraph("Body text with no dates")
        doc.save(str(f_header))
        actual = extract_received_date(f_header).received_date
        records.append(run_check("Received date in section header", "Section header with Received: 15 January 2025", "2025-01-15", actual))

        # Footer-based received date
        f_footer = temp_dir / "footer.docx"
        doc = docx.Document()
        doc.sections[0].footer.paragraphs[0].text = "Manuscript received on 15 Jan 2025. All rights reserved."
        doc.add_paragraph("Body text with no dates")
        doc.save(str(f_footer))
        actual = extract_received_date(f_footer).received_date
        records.append(run_check("Received date in section footer", "Section footer with Manuscript received on 15 Jan 2025", "2025-01-15", actual))

        # Corrupted DOCX file
        f_corrupt = temp_dir / "corrupted.docx"
        f_corrupt.write_bytes(b"\x00\x01\x02\x03\x04INVALID_ZIP_ARCHIVE_DATA")
        actual = extract_received_date(f_corrupt).received_date
        records.append(run_check("Corrupted DOCX binary handling", "Corrupted / non-zip binary docx", "invalid", actual))

        # Batch resilience (corrupted file alongside valid files)
        batch_dir = temp_dir / "batch_test"
        batch_dir.mkdir(exist_ok=True)
        doc_v1 = docx.Document()
        doc_v1.add_paragraph("Received: 10 January 2025")
        doc_v1.save(str(batch_dir / "valid1.docx"))

        (batch_dir / "bad.docx").write_bytes(b"CORRUPTED")

        doc_v2 = docx.Document()
        doc_v2.add_paragraph("Received: 20 January 2025")
        doc_v2.save(str(batch_dir / "valid2.docx"))

        batch_results = process_directory(batch_dir)
        b_map = {r.file: r.received_date for r in batch_results}
        batch_ok = (b_map.get("valid1.docx") == "2025-01-10" and
                    b_map.get("bad.docx") == "invalid" and
                    b_map.get("valid2.docx") == "2025-01-20")
        records.append(run_check(
            "Batch processing resilience",
            "Batch containing corrupted docx among valid files",
            "valid1:2025-01-10; bad:invalid; valid2:2025-01-20",
            f"valid1:{b_map.get('valid1.docx')}; bad:{b_map.get('bad.docx')}; valid2:{b_map.get('valid2.docx')}",
        ))

        # Temporary file exclusion
        (batch_dir / "~$temp_lock.docx").write_text("lock", encoding="utf-8")
        batch_results2 = process_directory(batch_dir)
        files_found = [r.file for r in batch_results2]
        records.append(run_check(
            "Temporary file exclusion (~$*)",
            "Directory containing ~$temp_lock.docx",
            "Excluded",
            "Excluded" if "~$temp_lock.docx" not in files_found else "Included",
        ))

        # =========================================================================
        # 5. CLI and CSV Output Generation
        # =========================================================================
        # CLI missing arguments
        cli_no_args = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True)
        records.append(run_check(
            "CLI argument validation (Missing arguments)",
            "python main.py",
            "Exit 1",
            f"Exit {cli_no_args.returncode}",
        ))

        # CLI nonexistent directory
        cli_bad_dir = subprocess.run(
            [sys.executable, "main.py", str(temp_dir / "missing_folder"), str(temp_dir / "out.csv")],
            capture_output=True,
            text=True,
        )
        records.append(run_check(
            "CLI directory validation (Nonexistent folder)",
            "python main.py <nonexistent_folder> <out.csv>",
            "Exit 1",
            f"Exit {cli_bad_dir.returncode}",
        ))

        # CLI CSV header verification
        cli_out_csv = temp_dir / "cli_output.csv"
        cli_ok = subprocess.run(
            [sys.executable, "main.py", str(batch_dir), str(cli_out_csv)],
            capture_output=True,
            text=True,
        )
        with open(cli_out_csv, mode="r", newline="", encoding="utf-8") as fp:
            csv_lines = list(csv.reader(fp))
        actual_header = ",".join(csv_lines[0]) if csv_lines else ""
        records.append(run_check(
            "Output CSV header format",
            "Generated CSV header line",
            "file,received_date",
            actual_header,
        ))

        # Deterministic sorting in CSV
        actual_order = [r[0] for r in csv_lines[1:]]
        expected_order = sorted(actual_order)
        records.append(run_check(
            "Deterministic alphabetical output ordering",
            "Output CSV file row ordering",
            ",".join(expected_order),
            ",".join(actual_order),
        ))

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Write test_report.csv
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["checks", "input", "expected", "actual", "result"])
        for rec in records:
            writer.writerow(rec)

    return records


def main():
    report_file = Path("test_report.csv")
    records = generate_report(report_file)

    passed = sum(1 for r in records if r[4] == "PASS")
    failed = sum(1 for r in records if r[4] == "FAIL")
    total = len(records)

    print(f"Generated test report at: {report_file.resolve()}")
    print(f"Total Checks: {total} | Passed: {passed} | Failed: {failed}")

    if failed > 0:
        print("\nFailed Checks:")
        for r in records:
            if r[4] == "FAIL":
                print(f"  - [{r[0]}] Input: '{r[1]}' | Expected: '{r[2]}' | Actual: '{r[3]}'")
        sys.exit(1)
    else:
        print("All quality assurance checks PASSED successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
