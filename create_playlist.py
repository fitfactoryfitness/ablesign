#!/usr/bin/env python3
"""
create_playlist.py

Builds the full weekly playlist schedule on all 3 real DRILLROOM screens
(TV1, TV3, TV5) in one run, from content already uploaded by
upload_content.py (under MONTH_FOLDER below) and the day/time windows in
schedule.csv. The screen<->tag mapping is fixed (screens.json), so there's
nothing to specify beyond --dry-run - meant to be launched once, overnight,
unattended.

Update MONTH_FOLDER (and SCHEDULE_CSV if it's ever named differently) each
month.

Adds items via POST, on top of whatever's already on each screen - run
delete_playlist.py first for a given screen if you want a clean slate on
that one.

Relaunch-safe: AbleSign rate-limits playlist writes to 15/min and 30/hour
PER SCREEN, so a full month's schedule can take a couple hours per screen.
Before adding anything to a screen, this script fetches what's already on
that screen's playlist and skips any (file, day, start, end) combo already
there. So if a run gets interrupted (pacing pause, closed terminal, crash,
...), just run the exact same command again - it picks up where it left
off, screen by screen, instead of creating duplicate items. Pacing itself
is handled by ablesign_common.py's throttle: it adds items until it's
about to hit the limit, sleeps until the window clears, then keeps going,
automatically.

Each AbleSign class subfolder is expected to hold up to 3 files, one per
TV1/TV3/TV5 tag (same convention as Drive).

schedule.csv only has Class/Day/Start/End columns - every row becomes a
plain weekly-recurring item for the whole month (see ablesign_common.py
docstring). Date-bounded swaps are done by hand in AbleSign.

Usage:
  python3 create_playlist.py --dry-run
  python3 create_playlist.py
"""

import argparse
import sys
import time

import ablesign_common as common

MONTH_FOLDER = "GROUP FITNESS/PACKAGE A"
SCHEDULE_CSV = "schedule.csv"


def _fmt_duration(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def run(screen, tag, folder, schedule_csv, duration, dry_run):
    """Core logic for one screen, also reused by test.py (Headquarter test
    run) and the web app backend. Returns (added_count,
    already_present_count, to_add_details) where to_add_details is
    [{"class","day","start","end"}] for every item this call added (or
    would add, in dry-run mode) - the web app's visual preview step uses
    this list directly instead of re-parsing printed text."""
    print(f"Target screen: {screen['title']} (id {screen['id']})")
    print(f"Using tag: {tag}\n")

    schedule = common.load_schedule(schedule_csv)
    folder_id = common.lookup_path(folder)
    class_folders = common.list_child_folders(folder_id)
    if not class_folders:
        print(f"No class subfolders found under AbleSign folder '{folder}'")
        return 0, 0, []

    # --- Pass 1: figure out the full worklist up front, so we can print a
    # total count and a time estimate before touching anything. ---
    work_items = []  # (class_name, day, start, end, media_id)
    for class_name, class_folder_id in class_folders:
        rows = schedule.get(class_name.strip().lower())
        if not rows:
            print(f"SKIP '{class_name}': no matching rows in {schedule_csv} (name mismatch?)")
            continue

        media_files = common.list_media_files(class_folder_id)
        media_id = next((mid for name, mid in media_files if common.tv_tag(name) == tag), None)
        if media_id is None:
            print(f"MISSING {tag} file for '{class_name}' in AbleSign folder '{folder}', skipping")
            continue

        for day, start, end in rows:
            work_items.append((class_name, day, start, end, media_id))

    existing = set() if dry_run else common.existing_playlist_signatures(screen["id"])

    to_add = []
    already_present = 0
    for class_name, day, start, end, media_id in work_items:
        day_key = common.DAY_ALIASES[day.lower()]
        sig = (media_id, day_key, start, end)
        if sig in existing:
            already_present += 1
        else:
            to_add.append((class_name, day, start, end, media_id, sig))

    print(f"\n{len(work_items)} schedule slot(s) matched across {len(class_folders)} folder(s).")
    print(f"  {already_present} already on the screen, {len(to_add)} to add this run.")
    if to_add and not dry_run:
        eta = len(to_add) / common.RATE_LIMIT_PER_HOUR * 3600
        print(
            f"  AbleSign allows roughly {common.RATE_LIMIT_PER_HOUR}/hour writes on this screen, so a "
            f"fresh run of {len(to_add)} item(s) takes roughly {_fmt_duration(eta)} if nothing else has "
            f"recently written to this screen. Safe to interrupt and rerun the same command any time - "
            f"already-added items are skipped automatically.\n"
        )

    # --- Pass 2: actually add, printing progress as we go. ---
    start_time = time.time()
    added_count = 0
    total_to_add = len(to_add)
    to_add_details = [
        {"class": class_name, "day": day, "start": start, "end": end}
        for class_name, day, start, end, media_id, sig in to_add
    ]

    for class_name, day, start, end, media_id, sig in to_add:
        if dry_run:
            print(f"[{added_count + 1}/{total_to_add}] would schedule {class_name}: {day} {start}-{end}")
            added_count += 1
            continue

        common.add_playlist_item(screen["id"], media_id, day, start, end, duration)
        existing.add(sig)
        added_count += 1

        elapsed = time.time() - start_time
        remaining = total_to_add - added_count
        # Simple sustained-rate estimate; the throttle's own "pacing..." print
        # already shows up live whenever it's actually waiting on the limit.
        eta = remaining / common.RATE_LIMIT_PER_HOUR * 3600
        print(
            f"[{added_count}/{total_to_add}] added {class_name}: {day} {start}-{end}  "
            f"(elapsed {_fmt_duration(elapsed)}, ~{_fmt_duration(eta)} left, {remaining} remaining)"
        )

    verb = "would add" if dry_run else "added"
    print(f"\nScreen done. {added_count} item(s) {verb}, {already_present} already present and skipped.")
    return added_count, already_present, to_add_details


def run_all_screens(folder, schedule_csv, duration, dry_run):
    """Loops run() over all 3 known screens (TV1/TV3/TV5 from screens.json).
    Reused by main() (CLI, hardcoded MONTH_FOLDER) and the web app backend
    (folder chosen by the user in the UI). Returns (total_added,
    total_already_present)."""
    screens = common.load_screens()  # {"TV1": 499083, "TV3": 499094, "TV5": 499095}

    total_added = 0
    total_already_present = 0

    for i, (tag, screen_id) in enumerate(screens.items(), start=1):
        screen = common.get_screen_by_id(screen_id)
        print(f"\n{'=' * 70}\n[{i}/{len(screens)}] {tag} -> {screen['title']} (id {screen_id})\n{'=' * 70}")
        added, already_present, _details = run(screen, tag, folder, schedule_csv, duration, dry_run)
        total_added += added
        total_already_present += already_present

    verb = "would add" if dry_run else "added"
    print(f"\n{'=' * 70}\nAll screens done. {total_added} item(s) {verb} in total, {total_already_present} already present and skipped.")
    return total_added, total_already_present


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List what would be scheduled on every screen, touch nothing in AbleSign",
    )
    args = parser.parse_args()
    run_all_screens(MONTH_FOLDER, SCHEDULE_CSV, common.DURATION, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
