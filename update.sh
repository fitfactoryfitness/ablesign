#!/usr/bin/env bash
# update.sh
#
# Run this before using any of the scripts. Pulls the latest version from
# GitHub and makes sure dependencies are installed - doesn't run anything
# else. After this finishes, run whichever script you need (see
# README.md for the list of commands).
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "==> Checking required tools..."
command -v git >/dev/null 2>&1 || { echo "git not found. Install Xcode Command Line Tools (macOS asks automatically the first time you run 'git') and re-run this script."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found. Install it ('brew install python') and re-run this script."; exit 1; }
if ! command -v rclone >/dev/null 2>&1; then
  echo "NOTE: rclone not found - 'Upload Content' and 'Update Program' won't work until it's installed and configured ('brew install rclone', then ask Lucas for the Drive remote setup). Everything else works fine without it."
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

echo ""
echo "All set. See README.md for which command to run next."
