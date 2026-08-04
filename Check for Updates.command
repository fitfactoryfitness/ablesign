#!/usr/bin/env bash
# Double-click this in Finder to pull the latest version and check
# everything's installed - no Terminal typing needed. Run this first,
# any time, before typing the command for whatever you actually want to
# do (see README.md).
cd "$(dirname "${BASH_SOURCE[0]}")"
bash update.sh
echo ""
read -p "Press Enter to close this window..."
