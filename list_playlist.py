#!/usr/bin/env python3
"""
list_playlist.py

Read-only: by default, prints only the media that should be showing on a
screen RIGHT NOW - based on this machine's current day/time AND, for any
item with a manually-set periodic date range (periodicScheduleEnabled /
scheduleStartDate / scheduleEndDate - the kind of swap you do by hand in
AbleSign, e.g. "weeks 1-2" vs "weeks 3-4"), whether today falls inside
that range. Pass --full to see the entire week's schedule instead (every
item, with its periodic date range annotated if it has one, unfiltered).

Straight from the AbleSign API, doesn't touch anything - safe to run any
time, including while create_playlist.py is mid-run on the same or a
different screen.

Usage:
  python3 list_playlist.py --screen-id 499083
  python3 list_playlist.py --screen-name "Headquarter"
  python3 list_playlist.py --screen-id 499083 --full
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
        "--full", action="store_true",
        help="Show the entire week's schedule instead of just what's live right now",
    )
    args = parser.parse_args()

    screen = common.resolve_screen(args.screen_id, args.screen_name)
    print(f"Screen: {screen['title']} (id {screen['id']})")

    current_day, current_time = common.current_day_and_time()
    if not args.full:
        day_full = common.DAY_NAMES[common.ALL_DAY_KEYS.index(current_day)]
        print(f"Right now: {day_full} {current_time} (this machine's clock)\n")
    else:
        print()

    rows = common.get_playlist_rows(screen["id"])
    if not rows:
        print("Playlist is empty.")
        return

    if not args.full:
        rows = [r for r in rows if common.is_row_live_now(r, current_day, current_time)]
        if not rows:
            print("Nothing scheduled for right now on this screen. Pass --full to see the whole week.")
            return

    day_order = {d: i for i, d in enumerate(common.ALL_DAY_KEYS)}
    rows.sort(key=lambda r: (day_order.get(r["day"], 99), r["start"] or ""))

    for r in rows:
        day_label = r["day"].capitalize() if r["day"] else "no active day"
        window = f"{r['start']}-{r['end']}" if r["start"] else "(no schedule set)"
        period_label = f"  [active {r['period_start']} to {r['period_end']}]" if r["period_start"] else ""
        skip_note = "  [OUT OF PERIODIC RANGE, not live]" if args.full and not r["periodic_ok"] else ""
        print(f"{day_label:10s} {window:14s} {r['title']}{period_label}{skip_note}  (item id {r['item_id']}, duration {r['duration']}s)")

    if args.full:
        print(f"\n{len(rows)} item(s) total.")
    else:
        print(f"\n{len(rows)} media currently live on this screen.")


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
