#!/bin/bash
# Auto-format the frontend (HTML/CSS/JS) with Prettier and apply safe ESLint fixes.
set -e
cd "$(dirname "$0")/.."

if [ ! -d node_modules ]; then
    echo "Installing frontend dev tools..."
    npm install --no-fund --no-audit
fi

echo "Formatting frontend with Prettier..."
npx prettier --write frontend

echo "Applying ESLint fixes..."
npx eslint frontend --fix

echo "Done."
