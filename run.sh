#!/usr/bin/env bash
set -euo pipefail

# Validate argument count
if [ "$#" -ne 2 ]; then
    echo "Error: Exactly two arguments required." >&2
    echo "Usage: ./run.sh <input_folder> <output.csv>" >&2
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_CSV="$2"

# Validate input directory exists
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory does not exist or is not a directory: $INPUT_DIR" >&2
    exit 1
fi

# Locate script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Locate Python interpreter (prefer python3.12, then python3, then python, verifying execution)
PYTHON_BIN=""
for candidate in python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys" >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "Error: Working Python interpreter not found in PATH." >&2
    exit 1
fi

# Check / install dependencies if missing
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

if ! "$PYTHON_BIN" -c "import docx, dateutil" >/dev/null 2>&1; then
    VENV_DIR="$SCRIPT_DIR/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        if "$PYTHON_BIN" -m venv "$VENV_DIR" >/dev/null 2>&1; then
            if [ -f "$VENV_DIR/bin/python" ]; then
                PYTHON_BIN="$VENV_DIR/bin/python"
            elif [ -f "$VENV_DIR/Scripts/python.exe" ]; then
                PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
            fi
        fi
    else
        if [ -f "$VENV_DIR/bin/python" ]; then
            PYTHON_BIN="$VENV_DIR/bin/python"
        elif [ -f "$VENV_DIR/Scripts/python.exe" ]; then
            PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
        fi
    fi

    if [ -f "$REQUIREMENTS_FILE" ]; then
        "$PYTHON_BIN" -m pip install -r "$REQUIREMENTS_FILE" >/dev/null 2>&1 || {
            echo "Error: Failed to install required dependencies from $REQUIREMENTS_FILE." >&2
            exit 1
        }
    fi
fi

# Execute the Python application and propagate exit code
exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" "$INPUT_DIR" "$OUTPUT_CSV"
