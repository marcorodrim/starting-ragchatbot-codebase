#!/bin/bash
# Verify frontend formatting and lint without modifying files (CI-friendly; non-zero exit on failure).
set -e
cd "$(dirname "$0")/.."

if [ ! -d node_modules ]; then
    echo "Installing frontend dev tools..."
    npm install --no-fund --no-audit
fi

echo "Checking frontend formatting (Prettier)..."
npx prettier --check frontend

echo "Linting frontend (ESLint)..."
npx eslint frontend

echo "All frontend quality checks passed."
