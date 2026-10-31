"""
Tests for Command-Line Interface, argument validation, and CSV output generation.
"""

import csv
import subprocess
import sys
from pathlib import Path
import pytest
from manusure.core import process_directory


class TestCliAndCsv:
    """Test CLI execution and CSV formatting."""

    def test_cli_missing_arguments(self):
        res = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True)
        assert res.returncode != 0
        assert "Usage" in res.stderr

    def test_cli_nonexistent_directory(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        out_csv = tmp_path / "output.csv"
        res = subprocess.run([sys.executable, "main.py", str(nonexistent), str(out_csv)], capture_output=True, text=True)
        assert res.returncode != 0
        assert "does not exist" in res.stderr

    def test_cli_end_to_end_success(self, tmp_path, create_docx):
        doc1 = create_docx("paper1.docx", paragraphs=["Received: 15 January 2025"])
        doc2 = create_docx("paper2.docx", paragraphs=["No received date mentioned"])
        out_csv = tmp_path / "out" / "output.csv"

        res = subprocess.run([sys.executable, "main.py", str(tmp_path), str(out_csv)], capture_output=True, text=True)
        assert res.returncode == 0
        assert out_csv.exists()

        with open(out_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        assert reader[0] == ["file", "received_date"]
        # Exactly 2 data rows
        rows = {r[0]: r[1] for r in reader[1:]}
        assert rows.get("paper1.docx") == "2025-01-15"
        assert rows.get("paper2.docx") == "invalid"

    def test_empty_folder_produces_header_only_csv(self, tmp_path):
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()
        out_csv = tmp_path / "empty_out.csv"

        process_directory(empty_dir, out_csv)
        assert out_csv.exists()

        with open(out_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        assert len(reader) == 1
        assert reader[0] == ["file", "received_date"]

    def test_deterministic_sorting(self, tmp_path, create_docx):
        create_docx("zeta.docx", paragraphs=["Received: 10 January 2025"])
        create_docx("alpha.docx", paragraphs=["Received: 12 January 2025"])
        create_docx("beta.docx", paragraphs=["Received: 14 January 2025"])

        out_csv = tmp_path / "sorted.csv"
        process_directory(tmp_path, out_csv)

        with open(out_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        filenames = [r[0] for r in reader[1:]]
        assert filenames == ["alpha.docx", "beta.docx", "zeta.docx"]

    def test_filenames_with_special_csv_characters(self, tmp_path, create_docx):
        special_name = "paper, with comma & 'quotes'.docx"
        create_docx(special_name, paragraphs=["Received: 20 January 2025"])

        out_csv = tmp_path / "special.csv"
        process_directory(tmp_path, out_csv)

        with open(out_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        assert len(reader) == 2
        assert reader[1][0] == special_name
        assert reader[1][1] == "2025-01-20"
