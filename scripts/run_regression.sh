#!/usr/bin/env sh
# Run regression tests for OCR -> Koinly conversion (macOS/Linux)
set -euo pipefail

# Determine original working directory and repo root (relative to this script)
ORIG_DIR="$(pwd)"
ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"

# Inform the user if we weren't invoked from the repo root and switch
if [ "$ORIG_DIR" != "$ROOT_DIR" ]; then
	echo "Note: invoked from '$ORIG_DIR'. Switching to repo root '$ROOT_DIR'."
fi
cd "$ROOT_DIR"

echo "Running regression tests (using virtualenv if available)..."

# Prefer project virtualenv pytest
PYTEST="./.venv/bin/pytest"
if [ ! -x "$PYTEST" ]; then
	# Fallback to system pytest
	PYTEST="pytest"
fi

# Run regression tests (package should be installed in development mode)
# No need for PYTHONPATH manipulation when using 'pip install -e .'
"$PYTEST" -q \
	tests/test_regression_error1.py \
	tests/test_regression_error2.py \
	tests/test_regression_eth.py \
	tests/test_regression_data_dir.py \
	tests/test_end_to_end.py

echo "Regression tests completed."
