#!/usr/bin/env python3
"""
update_program.py

Refreshes ONE program/class's slides everywhere, without touching anything
else: pulls new files from Drive, uploads them into AbleSign under a new
"vN" version folder (old files stay in place, untouched, as a recoverable
history), then on all 3 real screens (TV1/TV3/TV5) removes just the old
playlist items for this program and adds new ones from the new version,
using the same day/time windows already in schedule.csv.

--program must match, case-insensitively:
  - the Drive subfolder name under the month folder
    (Programming/<month>/<program>)
  - the existing AbleSign folder name under GROUP FITNESS/<month>
    (must already exist - run upload_content.py/Upload Content for this
    month first if it doesn't)
  - a Class name in schedule.csv (its existing day/time rows are reused
    as-is; this script never edits schedule.csv)

Versioning is automatic: the first run creates "v2" (the original,
un-versioned files at the folder root count as the implicit "v1"); a
second run against the same program creates "v3", and so on. Nothing is
ever overwritten.

A TV whose new file is missing (e.g. Drive only had TV1+TV3, not TV5) is
left completely untouched for this program - no removal, no addition -
rather than risk leaving that TV with a gap.

Before touching anything, it compares what's ACTUALLY live on the 3
screens right now for this program against what schedule.csv says. If
they match, it proceeds silently. If they don't (a manual AbleSign edit,
a missed re-push, ...), it prints exactly what's mismatched and asks
you to confirm before continuing - otherwise it would silently apply
schedule.csv's times to the new slides even though that's not actually
what's live today.

Usage:
  python3 update_program.py --month "8. August" --program "ABS ASSAULT" --dry-run
  python3 update_program.py --month "8. August" --program "ABS ASSAULT" --yes
"""

import argparse
import re
import sys
import tempfile

import ablesign_common as common

VERSION_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)


def _active_windows(item):
    """[(day, 'HH:MM', 'HH:MM'), ...] for a raw GET-shaped playlist item."""
    windows = []
    for day in common.ALL_DAY_KEYS:
        start = (item.get(f"{day}Start") or "00:00:00")[:5]
        end = (item.get(f"{day}End") or "00:00:00")[:5]
        if not (start == "00:00" and end == "00:00"):
            windows.append((day, start, end))
    return windows


def _check_live_matches_schedule(screens, old_media_ids, rows, dry_run):
    """Compares what's ACTUALLY live right now (the old items about to be
    swapped) against what schedule.csv says for this program. If AbleSign's
    live schedule has drifted from schedule.csv - a manual edit, a missed
    re-push, whatever - blindly swapping media at schedule.csv's times
    would silently change the times too, not just the picture. Real runs
    stop and ask before proceeding; dry runs just report it.

    Returns True if it's fine to proceed, False if the user aborted."""
    expected = {(common.DAY_ALIASES[day.lower()], start, end) for day, start, end in rows}

    mismatched = {}
    for tag, screen_id in screens.items():
        playlist = common.get_playlist(screen_id)
        live = set()
        for item in playlist.get("items", []):
            if item.get("mediafileId") in old_media_ids:
                live.update(_active_windows(item))
        if live != expected:
            mismatched[tag] = live

    if not mismatched:
        print("Live schedule matches schedule.csv for this program on all 3 screens.\n")
        return True

    print("WARNING: what's currently live doesn't match schedule.csv for this program.")
    print(f"  schedule.csv expects: {sorted(expected)}")
    for tag, live in mismatched.items():
        screen = common.get_screen_by_id(screens[tag])
        print(f"  {tag} ({screen['title']}) is currently live at: {sorted(live)}")
    print()

    if dry_run:
        print("(dry run - the real run would stop here and ask before proceeding)\n")
        return True

    answer = input("Continue anyway and use schedule.csv's times for the new slides? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted - nothing uploaded or changed.")
        return False
    print()
    return True


def run(month, program, schedule_csv, dry_run):
    print(f"Month: {month}")
    print(f"Program: {program}\n")

    print("Looking for the program's Drive folder...")
    month_folders = common.rclone_list_subfolders(common.PARENT_DRIVE_FOLDER_ID)
    month_id = next((fid for name, fid in month_folders if name.strip().lower() == month.strip().lower()), None)
    if month_id is None:
        available = ", ".join(name for name, _ in month_folders)
        raise common.AbleSignError(f"No Drive subfolder named '{month}' found. Available: {available}")

    program_folders = common.rclone_list_subfolders(month_id)
    drive_program_id = next((fid for name, fid in program_folders if name.strip().lower() == program.strip().lower()), None)
    if drive_program_id is None:
        available = ", ".join(name for name, _ in program_folders)
        raise common.AbleSignError(f"No Drive subfolder named '{program}' found under '{month}'. Available: {available}")

    # Schedule rows for this program - fail fast, before touching Drive/AbleSign, if there's nothing to schedule.
    schedule = common.load_schedule(schedule_csv)
    rows = schedule.get(program.strip().lower())
    if not rows:
        raise common.AbleSignError(f"No rows for '{program}' in {schedule_csv} (name mismatch?)")

    # AbleSign folder must already exist - this script updates content, it doesn't set up a new program.
    program_folder_id = common.lookup_path(f"GROUP FITNESS/{month}/{program}")

    existing_children = common.list_child_folders(program_folder_id)
    existing_versions = [int(m.group(1)) for title, _fid in existing_children if (m := VERSION_RE.match(title.strip()))]
    next_version = max(existing_versions, default=1) + 1
    version_name = f"v{next_version}"
    print(f"Next version folder: {version_name}\n")

    # Every media file currently associated with this program (root + every existing version folder)
    # is a candidate for removal from the TVs - covers repeated runs where the "old" content is
    # itself a previous version, not just the original root-level files.
    old_media_ids = {mid for _name, mid in common.list_media_files(program_folder_id)}
    for _title, folder_id in existing_children:
        old_media_ids |= {mid for _name, mid in common.list_media_files(folder_id)}
    print(f"{len(old_media_ids)} existing media file(s) associated with this program across all versions.\n")

    screens = common.load_screens()  # {"TV1": id, "TV3": id, "TV5": id}

    if not _check_live_matches_schedule(screens, old_media_ids, rows, dry_run):
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        common.rclone_pull_folder(drive_program_id, tmpdir)
        filenames = common.list_local_files(tmpdir)
        if not filenames:
            raise common.AbleSignError(f"Drive folder '{program}' under '{month}' is empty.")

        new_files = {}
        for name in filenames:
            tag = common.tv_tag(name)
            if tag:
                new_files[tag] = name
            else:
                print(f"WARNING: '{name}' has no TV1/TV3/TV5 tag, skipping this file")
        if not new_files:
            raise common.AbleSignError(f"None of the files in '{program}' are tagged TV1/TV3/TV5.")
        print(f"New files found: {new_files}\n")

        if dry_run:
            print(f"Would create AbleSign folder '{version_name}' under '{program}' and upload: {list(new_files.values())}\n")
            for tag, screen_id in screens.items():
                screen = common.get_screen_by_id(screen_id)
                if tag not in new_files:
                    print(f"{tag} ({screen['title']}): no new file for this tag - would leave untouched")
                    continue
                playlist = common.get_playlist(screen_id)
                to_remove = [it for it in playlist.get("items", []) if it.get("mediafileId") in old_media_ids]
                print(f"{tag} ({screen['title']}): would remove {len(to_remove)} old item(s), add {len(rows)} new item(s)")
            print("\nDry run - nothing uploaded or changed in AbleSign.")
            return

        version_folder_id, _created = common.get_or_create_folder(version_name, program_folder_id)
        new_media_ids = {}
        for tag, fname in new_files.items():
            data, mimetype = common.read_file(tmpdir, fname)
            media_id = common.upload_media(fname, mimetype, data, version_folder_id)
            new_media_ids[tag] = media_id
            print(f"  uploaded {fname} -> media id {media_id} (folder {version_name})")

    print()
    for tag, screen_id in screens.items():
        screen = common.get_screen_by_id(screen_id)
        if tag not in new_media_ids:
            print(f"{tag} ({screen['title']}): no new file for this tag, leaving existing schedule untouched")
            continue

        removed = common.remove_playlist_items(screen_id, old_media_ids)
        print(f"{tag} ({screen['title']}): removed {removed} old item(s)")

        media_id = new_media_ids[tag]
        existing_sigs = common.existing_playlist_signatures(screen_id)
        added = 0
        for day, start, end in rows:
            day_key = common.DAY_ALIASES[day.lower()]
            sig = (media_id, day_key, start, end)
            if sig in existing_sigs:
                continue
            common.add_playlist_item(screen_id, media_id, day, start, end, common.DURATION)
            added += 1
        print(f"{tag} ({screen['title']}): added {added} new item(s)")

    print("\nDone.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--month", required=True, help='Drive month folder name, e.g. "8. August"')
    parser.add_argument("--program", required=True, help='Program/class folder name, e.g. "ABS ASSAULT"')
    parser.add_argument("--schedule-csv", default="schedule.csv", help="Local CSV exported from AI SCHEDULE")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would change, touch nothing in AbleSign",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Required to actually run (without --dry-run), confirms you mean it",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        parser.error("--yes is required to actually run this (or pass --dry-run to preview)")

    run(args.month, args.program, args.schedule_csv, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
