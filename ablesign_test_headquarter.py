#!/usr/bin/env python3
"""
ablesign_test_headquarter.py

One-off validation run for the Headquarter TV (screen id 498279) ahead of
the real switch. Pulls ONLY the TV1-tagged slide from each Drive class
folder (TV3/TV5 files are ignored entirely), uploads it into the same
Claude/8. August folder mirror the real batch script uses, and schedules
it using schedule.csv, exactly like production would for TV1, just aimed
at Headquarter instead of the real DRILLROOM screen.

This exists to prove the full pipeline (optionally: clear existing
playlist -> mirror Drive folders -> upload -> schedule) works before
trusting it against TV1/TV3/TV5 for real.

Usage:
  python3 ablesign_test_headquarter.py \
      --drive-folder-id 1l_C_uoSo2Rkln2QsMlj85wKnEh92Jg__ \
      --ablesign-root "Claude/8. August" \
      --schedule-csv schedule.csv \
      --dry-run

Drop --dry-run once the printed plan looks right.

Add --clear-first --yes-really-clear to also wipe Headquarter's existing
playlist before pushing, the same UNVERIFIED clear mechanism the real
switch will use on TV1/TV3/TV5, this is exactly what you want to prove
works tonight rather than find out tomorrow.
"""

import argparse
import sys
import tempfile

import ablesign_batch as base

HEADQUARTER_SCREEN_ID = 498279


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--drive-folder-id", required=True, help="Drive ID of the month folder")
    parser.add_argument("--ablesign-root", required=True, help='e.g. "Claude/8. August"')
    parser.add_argument("--schedule-csv", required=True, help="Local CSV exported from AI SCHEDULE")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List what would happen, touch nothing in AbleSign",
    )
    parser.add_argument(
        "--clear-first", action="store_true",
        help="Wipe Headquarter's existing playlist before pushing. UNVERIFIED endpoint, "
             "see the NOTE comments in ablesign_batch.py. Requires --yes-really-clear.",
    )
    parser.add_argument(
        "--yes-really-clear", action="store_true",
        help="Required alongside --clear-first, confirms you mean it",
    )
    args = parser.parse_args()

    if args.clear_first:
        if args.dry_run:
            print(f"Would clear playlist on Headquarter (screen {HEADQUARTER_SCREEN_ID})\n")
        else:
            if not args.yes_really_clear:
                sys.exit("--clear-first also requires --yes-really-clear")
            print(f"Clearing existing playlist on Headquarter (screen {HEADQUARTER_SCREEN_ID})...")
            base.clear_playlist(HEADQUARTER_SCREEN_ID)
            print()

    schedule = base.load_schedule(args.schedule_csv)
    class_folders = base.rclone_list_subfolders(args.drive_folder_id)
    if not class_folders:
        sys.exit(f"No subfolders found in Drive folder {args.drive_folder_id}")

    ablesign_root_id = None if args.dry_run else base.resolve_ablesign_root(args.ablesign_root)

    for class_name, drive_id in class_folders:
        key = class_name.strip().lower()
        rows = schedule.get(key)
        if not rows:
            print(f"SKIP '{class_name}': no matching rows in {args.schedule_csv} (name mismatch?)")
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            base.rclone_pull_folder(drive_id, tmpdir)
            filenames = base.list_local_files(tmpdir)

            tv1_file = None
            for name in filenames:
                if base.tv_tag(name) == "TV1":
                    tv1_file = name
                    break
                if base.tv_tag(name) is None:
                    print(f"  WARNING: '{name}' in '{class_name}' has no TV1/TV3/TV5 tag, skipping this file")

            if not tv1_file:
                print(f"  MISSING TV1 file for '{class_name}', skipping")
                continue

            print(f"\n{class_name}: {len(rows)} schedule slot(s), TV1 file: {tv1_file}")

            if args.dry_run:
                for day, start, end in rows:
                    print(f"  would schedule {day} {start}-{end} on Headquarter")
                continue

            folder_id = base.get_or_create_ablesign_folder(class_name, ablesign_root_id)
            data, mimetype = base.read_file(tmpdir, tv1_file)
            media_id = base.upload_media(tv1_file, mimetype, data, folder_id)
            print(f"  uploaded {tv1_file} -> media_files id {media_id} (AbleSign folder {folder_id})")
            for day, start, end in rows:
                base.add_playlist_item(HEADQUARTER_SCREEN_ID, media_id, day, start, end)
                print(f"    added to Headquarter for {day} {start}-{end}")

    print("\nDone.")


if __name__ == "__main__":
    main()
