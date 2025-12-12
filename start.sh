#!/bin/bash
# CINDERGRACE GUI Launcher with automatic venv management

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════╗"
echo "║       CINDERGRACE Pipeline Control - GUI           ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10 or higher."
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Virtual environment not found. Creating..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install/update dependencies
echo "📚 Checking and updating dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✓ Dependencies up to date"
echo ""

# Check if workflow templates exist
WORKFLOW_DIR="config/workflow_templates"
WORKFLOW_COUNT=$(find "$WORKFLOW_DIR" -name "*.json" -type f 2>/dev/null | wc -l)

if [ "$WORKFLOW_COUNT" -eq 0 ]; then
    echo "⚠️  No workflow templates found in $WORKFLOW_DIR"
    echo "   Please add your ComfyUI workflow JSON files there."
    echo "   See $WORKFLOW_DIR/README.md for instructions."
    echo ""
else
    echo "✓ Found $WORKFLOW_COUNT workflow template(s)"
    echo ""
fi

# Check if ComfyUI is running
echo "🔌 Checking ComfyUI connection..."
if curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "✓ ComfyUI is running at http://127.0.0.1:8188"
    echo ""
else
    echo "⚠️  ComfyUI not detected at http://127.0.0.1:8188"
    echo ""
    echo "   To start ComfyUI, run in a separate terminal:"
    echo "   cd /path/to/ComfyUI && python main.py"
    echo ""
    read -p "   Continue anyway? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
        echo "Aborted."
        exit 1
    fi
    echo ""
fi

# Launch GUI
echo "🚀 Launching CINDERGRACE GUI..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   🌐 Open your browser at: http://127.0.0.1:7860"
echo ""
echo "   Press Ctrl+C to stop the GUI"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python main.py

# Deactivate venv on exit
deactivate
