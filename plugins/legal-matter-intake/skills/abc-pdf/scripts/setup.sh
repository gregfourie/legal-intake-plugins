#!/bin/bash
# setup.sh — Auto-install all PDF extraction dependencies into a local venv.
# Idempotent: safe to run every time. Skips engines already installed.
# Creates .venv/ inside SKILL_DIR (the directory containing this script's parent).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SKILL_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"

echo "=== abc-pdf setup ==="
echo "Skill directory: $SKILL_DIR"

# ---------- Python venv ----------
if [ ! -f "$VENV_PY" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_PY" -m pip install --upgrade pip --quiet
    echo "Virtual environment created at $VENV_DIR"
else
    echo "Virtual environment already exists."
fi

# ---------- Core: pdfplumber (always needed) ----------
if "$VENV_PY" -c "import pdfplumber" 2>/dev/null; then
    echo "[OK] pdfplumber already installed"
else
    echo "Installing pdfplumber..."
    "$VENV_PY" -m pip install pdfplumber --quiet
    echo "[OK] pdfplumber installed"
fi

# ---------- pdf-inspector (triage probe only — NOT an extraction engine) ----------
# Pure-Rust, offline, no network capability. Used by scripts/pdfi_probe.py for
# fast classification, per-page OCR routing and broken-font-encoding detection.
# Its Markdown output is deliberately never used: it wraps hanging-indent legal
# prose in table pipes and inlines footnote markers into the text.
PDFI_OK=false
if "$VENV_PY" -c "import pdf_inspector" 2>/dev/null; then
    echo "[OK] pdf-inspector already installed"
    PDFI_OK=true
else
    echo "Installing pdf-inspector (triage probe)..."
    if "$VENV_PY" -m pip install "pdf-inspector>=0.2.6" --quiet 2>/dev/null; then
        PDFI_OK=true
        echo "[OK] pdf-inspector installed"
    else
        echo "[SKIP] pdf-inspector install failed (non-fatal — triage falls back to pdfplumber)"
    fi
fi

# ---------- pytesseract (fast OCR fallback) ----------
TESSERACT_OK=false
if "$VENV_PY" -c "import pytesseract" 2>/dev/null; then
    echo "[OK] pytesseract already installed"
    TESSERACT_OK=true
else
    echo "Installing pytesseract + Pillow..."
    "$VENV_PY" -m pip install pytesseract Pillow pdf2image --quiet && TESSERACT_OK=true
    if $TESSERACT_OK; then
        echo "[OK] pytesseract installed"
    else
        echo "[SKIP] pytesseract install failed (non-fatal)"
    fi
fi

# Check if tesseract binary is available
if command -v tesseract &>/dev/null; then
    echo "[OK] tesseract binary found: $(command -v tesseract)"
else
    echo "[WARN] tesseract binary not found — pytesseract engine won't work"
    echo "       Install via: apt install tesseract-ocr (Linux) or brew install tesseract (macOS)"
    # Try installing on Linux (Cowork / Ubuntu)
    if [ -f /etc/debian_version ]; then
        echo "Attempting to install tesseract-ocr via apt..."
        if sudo apt-get install -y tesseract-ocr poppler-utils 2>/dev/null; then
            echo "[OK] tesseract-ocr installed via apt"
        else
            echo "[SKIP] Could not install tesseract-ocr (non-fatal)"
        fi
    fi
fi

# Check poppler (needed by pdf2image for pytesseract)
if command -v pdftoppm &>/dev/null; then
    echo "[OK] poppler-utils (pdftoppm) found"
else
    echo "[WARN] poppler-utils not found — needed by pdf2image"
    if [ -f /etc/debian_version ]; then
        echo "Attempting to install poppler-utils..."
        sudo apt-get install -y poppler-utils 2>/dev/null && echo "[OK] poppler-utils installed" || echo "[SKIP] Could not install poppler-utils"
    fi
fi

# ---------- Docling (heavy OCR + layout engine) ----------
DOCLING_OK=false
if "$VENV_PY" -c "from docling.document_converter import DocumentConverter" 2>/dev/null; then
    echo "[OK] docling already installed"
    DOCLING_OK=true
else
    echo "Installing docling (this may take 2-5 minutes)..."
    if "$VENV_PY" -m pip install docling --quiet 2>/dev/null; then
        DOCLING_OK=true
        echo "[OK] docling installed"
    else
        echo "[SKIP] docling install failed (non-fatal — pytesseract will be used for OCR)"
    fi
fi

# ---------- liteparse (Tesseract.js OCR via Node) ----------
LITEPARSE_OK=false
if command -v lit &>/dev/null || command -v liteparse &>/dev/null; then
    echo "[OK] liteparse already installed"
    LITEPARSE_OK=true
else
    if command -v npm &>/dev/null; then
        echo "Installing liteparse via npm..."
        if npm i -g @llamaindex/liteparse 2>/dev/null; then
            LITEPARSE_OK=true
            echo "[OK] liteparse installed"
        else
            echo "[SKIP] liteparse install failed (non-fatal)"
        fi
    else
        echo "[SKIP] npm not found — liteparse requires Node.js >= 18"
    fi
fi

# ---------- Summary ----------
echo ""
echo "=== Engine availability ==="
echo "  pdfplumber:  OK (always available)"
if $PDFI_OK; then
    echo "  pdf-inspector: OK (triage probe only, not an extraction engine)"
else
    echo "  pdf-inspector: UNAVAILABLE (triage falls back to pdfplumber page walk)"
fi
if $TESSERACT_OK && command -v tesseract &>/dev/null; then
    echo "  pytesseract: OK"
else
    echo "  pytesseract: UNAVAILABLE"
fi
if $DOCLING_OK; then
    echo "  docling:     OK"
else
    echo "  docling:     UNAVAILABLE"
fi
if $LITEPARSE_OK; then
    echo "  liteparse:   OK"
else
    echo "  liteparse:   UNAVAILABLE"
fi
echo ""
echo "Setup complete. Use: $VENV_PY to run Python scripts."
