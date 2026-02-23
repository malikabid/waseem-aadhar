#!/bin/bash

# ID Card Generator - Local Startup Script
# This script starts the FastAPI server and opens the app in your browser

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 Starting ID Card Generator..."
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Warning: Virtual environment not found."
    echo "    Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
fi

echo ""
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "📄 API Docs available at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server and open browser in the background
(
    sleep 3
    if command -v open &> /dev/null; then
        # macOS
        open http://localhost:8000
    elif command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open http://localhost:8000
    elif command -v start &> /dev/null; then
        # Windows
        start http://localhost:8000
    fi
) &

# Run the app
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
