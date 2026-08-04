#!/usr/bin/env bash
# start_app.sh
#
# One-command launcher for the AbleSign Control Panel. Meant for anyone on
# the team: pulls the latest code, installs whatever's missing, then starts
# the app. Safe to run repeatedly - every step is a no-op if already done.
#
# Usage:
#   bash start_app.sh
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "==> Checking required tools..."
command -v git >/dev/null 2>&1 || { echo "git not found. Install Xcode Command Line Tools (macOS asks automatically the first time you run 'git') and re-run this script."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js not found. Install it from https://nodejs.org (or 'brew install node') and re-run this script."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm not found (normally comes with Node.js). Install Node.js and re-run this script."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found. Install it ('brew install python') and re-run this script."; exit 1; }
if ! command -v rclone >/dev/null 2>&1; then
  echo "NOTE: rclone not found - 'Upload Content' won't work until it's installed and configured ('brew install rclone', then ask Lucas for the Drive remote setup). Every other page works fine without it."
fi

echo ""
echo "==> Checking for an AbleSign API key..."
if [ -z "$ABLESIGN_API_KEY" ] && [ ! -s .ablesign_api_key ]; then
  echo "No API key found. Ask Lucas for the current AbleSign API key, then either:"
  echo "  - create a file named .ablesign_api_key in this folder containing just the key, or"
  echo "  - export ABLESIGN_API_KEY=... in your shell profile"
  exit 1
fi

echo ""
echo "==> Checking for updates..."
if [ -d .git ]; then
  git fetch --quiet
  LOCAL=$(git rev-parse @)
  REMOTE=$(git rev-parse '@{u}' 2>/dev/null || echo "$LOCAL")
  if [ "$LOCAL" = "$REMOTE" ]; then
    echo "Already up to date."
  elif [ -n "$(git status --porcelain)" ]; then
    echo "You have local changes AND the remote has new commits - not auto-pulling to avoid a conflict."
    echo "Run 'git status' to see what's changed, commit or stash it, then 'git pull' manually."
  else
    echo "Pulling latest changes..."
    git pull
  fi
else
  echo "Not a git repository - skipping update check."
fi

echo ""
echo "==> Installing Python dependencies..."
python3 -m pip install --quiet -r requirements.txt
python3 -m pip install --quiet -r webapp/backend/requirements.txt

echo ""
echo "==> Installing frontend dependencies..."
(cd webapp/frontend && npm install --no-fund --no-audit)

echo ""
echo "==> Starting the app..."
echo "Once you see 'ready', open http://127.0.0.1:5173 in your browser."
echo "Press Ctrl+C to stop."
echo ""
cd webapp && bash dev.sh
