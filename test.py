#!/usr/bin/env python3
"""
test.py

Convenience wrapper around create_playlist.py: pushes every TV1-tagged
slide onto the Headquarter screen (id 498279), for testing the pipeline
before trusting it against the real DRILLROOM screens (TV1/TV3/TV5).

Same underlying logic as create_playlist.py (see that file's docstring
for the rate-limit pacing and relaunch-safe/no-duplicates behavior) - this
script just hardcodes screen=Headquarter and --tv-tag=TV1 so you don't
have to remember them.

Run delete_playlist.py --screen-id 498279 first if you want Headquarter
cleared before this test run.

Usage:
  python3 test.py --folder "Claude/8. August" --dry-run
  python3 test.py --folder "Claude/8. August"
"""

import argparse
import sys

import ablesign_common as common
import create_playlist


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--folder", default="Claude/8. August",
        help='AbleSign folder path, e.g. "Claude/8. August" (default: "Claude/8. August")',
    )
    parser.add_argument("--schedule-csv", default="schedule.csv", help="Local CSV exported from AI SCHEDULE")
    parser.add_argument("--duration", type=int, default=common.DURATION, help=f"Display duration in seconds (default {common.DURATION})")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List what would be scheduled, touch nothing in AbleSign",
    )
    args = parser.parse_args()

    screen = common.get_screen_by_id(common.HEADQUARTER_SCREEN_ID)
    create_playlist.run(screen, "TV1", args.folder, args.schedule_csv, args.duration, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
