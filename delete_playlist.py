#!/usr/bin/env python3
"""
delete_playlist.py

Clears every existing item from one screen's playlist. Run this before
create_playlist.py when you want a clean slate rather than appending on
top of whatever's already scheduled.

Uses PUT /screens/{id}/playlist with an empty items array - confirmed
against the live AbleSign API docs (there is no per-item DELETE endpoint,
despite what earlier scripts in this folder guessed).

Usage:
  python3 delete_playlist.py --screen-id 499083 --dry-run
  python3 delete_playlist.py --screen-id 499083 --yes

  python3 delete_playlist.py --screen-name "Headquarter" --yes
"""

import argparse
import sys

import ablesign_common as common


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--screen-id", type=int, help="AbleSign screen id")
    group.add_argument("--screen-name", help="AbleSign screen title")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show the target screen and current item count, touch nothing in AbleSign",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Required to actually clear (without --dry-run), confirms you mean it",
    )
    args = parser.parse_args()

    screen = common.resolve_screen(args.screen_id, args.screen_name)
    print(f"Target screen: {screen['title']} (id {screen['id']})")

    if args.dry_run:
        playlist = common.get_playlist(screen["id"])
        print(f"Would clear {len(playlist.get('items', []))} existing playlist item(s).")
        return

    if not args.yes:
        parser.error("--yes is required to actually clear a playlist (or pass --dry-run to preview)")

    common.clear_playlist(screen["id"])
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
