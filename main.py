#!/usr/bin/env python3
"""
ManuSure - Command-Line Interface
Usage:
    python main.py <input_folder> <output.csv>
"""

import sys
from pathlib import Path
from manusure.core import process_directory


def main() -> int:
    """CLI entrypoint."""
    if len(sys.argv) != 3:
        sys.stderr.write("Error: Exactly two arguments required.\n")
        sys.stderr.write("Usage: python main.py <input_folder> <output.csv>\n")
        return 1

    input_folder = sys.argv[1]
    output_csv = sys.argv[2]

    in_path = Path(input_folder)
    if not in_path.exists():
        sys.stderr.write(f"Error: Input directory does not exist: {input_folder}\n")
        return 1

    if not in_path.is_dir():
        sys.stderr.write(f"Error: Input path is not a directory: {input_folder}\n")
        return 1

    try:
        process_directory(in_path, output_csv)
    except Exception as exc:
        sys.stderr.write(f"Error processing manuscripts: {exc}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
