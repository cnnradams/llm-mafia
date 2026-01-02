#!/bin/bash
# Run the backend server

set -e  # Exit on error

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
# Use Python 3.12 for pydantic-core wheel compatibility
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with Python 3.12..."
    python3.12 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if uvicorn is installed, install dependencies if not
if [ ! -f "venv/bin/uvicorn" ]; then
    echo "Upgrading pip..."
    pip install --upgrade pip
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    echo "Dependencies already installed, skipping..."
fi

# Use the venv's uvicorn directly to avoid PATH issues
echo "Starting server..."
exec venv/bin/uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

