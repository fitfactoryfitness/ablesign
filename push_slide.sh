#!/usr/bin/env bash
# push_slide.sh — pull a Drive folder down with rclone, then push it to
# AbleSign. Single command, no GCP project needed.
#
# Usage:
#   ./push_slide.sh "Testing/LOUNGE MAIN SCREEN" --day fri --start 09:00 --end 12:00
#   ./push_slide.sh "Testing/LOUNGE MAIN SCREEN" --day fri --start 09:00 --end 12:00 --dry-run
#
# Requires: rclone configured with a remote named "gdrive" (see README.md),
# and ABLESIGN_API_KEY set in your environment.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 \"<Drive path, e.g. Testing/LOUNGE MAIN SCREEN>\" [ablesign_push.py args...]"
  exit 1
fi

DRIVE_PATH="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "Pulling '$DRIVE_PATH' from Drive via rclone..."
rclone copy "gdrive:$DRIVE_PATH" "$TMPDIR"

SCREEN_NAME="$(basename "$DRIVE_PATH")"

python3 "$SCRIPT_DIR/ablesign_push.py" \
  --folder "$TMPDIR" \
  --screen-name "$SCREEN_NAME" \
  "$@"
