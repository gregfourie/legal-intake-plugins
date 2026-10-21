#!/bin/bash
# Run liteparse on a PDF and save output to the extraction directory.
# Usage: run_liteparse.sh <pdf_path> <extract_dir>

set -e

PDF_PATH="$1"
EXTRACT_DIR="$2"

if [ -z "$PDF_PATH" ] || [ -z "$EXTRACT_DIR" ]; then
    echo "Usage: run_liteparse.sh <pdf_path> <extract_dir>" >&2
    exit 1
fi

if [ ! -f "$PDF_PATH" ]; then
    echo "ERROR: PDF not found: $PDF_PATH" >&2
    exit 1
fi

# Check liteparse is available
LIT_CMD=""
if command -v lit &>/dev/null; then
    LIT_CMD="lit"
elif command -v liteparse &>/dev/null; then
    LIT_CMD="liteparse"
else
    echo "ERROR: liteparse not installed. Run: npm i -g @llamaindex/liteparse" >&2
    exit 1
fi

mkdir -p "$EXTRACT_DIR"

START=$(date +%s)

# Run liteparse — output as text (default), quiet mode.
# Capture stderr instead of discarding it: liteparse has been observed to fail
# silently (exit non-zero or write nothing) with stderr suppressed, leaving the
# pipeline to believe the engine ran.
ERRLOG="$EXTRACT_DIR/liteparse_stderr.log"
if ! "$LIT_CMD" parse "$PDF_PATH" -q -o "$EXTRACT_DIR/liteparse_output.md" 2>"$ERRLOG"; then
    echo "ERROR: liteparse exited non-zero. stderr:" >&2
    cat "$ERRLOG" >&2
    exit 1
fi

# Fail loudly on missing or empty output — an engine that produced nothing must
# not count as having succeeded.
if [ ! -s "$EXTRACT_DIR/liteparse_output.md" ]; then
    echo "ERROR: liteparse produced no output (missing or empty liteparse_output.md). stderr:" >&2
    cat "$ERRLOG" >&2 2>/dev/null || true
    exit 1
fi
rm -f "$ERRLOG"

END=$(date +%s)
ELAPSED=$((END - START))

CHARS=$(wc -c < "$EXTRACT_DIR/liteparse_output.md" | tr -d ' ')

echo "liteparse done in ${ELAPSED}s, ${CHARS} chars"
echo "Output: $EXTRACT_DIR/liteparse_output.md"
