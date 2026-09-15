#!/usr/bin/env python3
"""
upload_content.py

Mirrors one month's class slides from Drive into AbleSign, under
GROUP FITNESS/<month>. Does NOT touch any screen's playlist - that's
create_playlist.py's job, run separately once content is uploaded.

Drive source: the fixed "Programming" parent folder
(https://drive.google.com/drive/folders/1sm9n_jKbWJEkBd-ziiyBTrvjbwJyK-ye),
under which each month has its own subfolder (e.g. "8. August"). You just
name the month; the Drive subfolder and the AbleSign destination folder
(GROUP FITNESS/<month>) are both derived from that one name.

Usage:
  python3 upload_content.py --month "8. August" --dry-run
  python3 upload_content.py --month "8. August"

  # Just specific classes, instead of the whole month (won't re-touch/
  # duplicate anything already uploaded for classes not listed):
  python3 upload_content.py --month "PACKAGE A" --programs "ATH CON SPEED W12,ATH CON SPEED W34" --dry-run
"""

import argparse
import shutil
import sys
import tempfile

import ablesign_common as common


def run(month, dry_run, programs=None):
    """Core logic, also called directly by the web app backend. Returns
    the number of files uploaded (or that would be uploaded, if dry_run).

    programs: optional list of exact class-folder names (case-insensitive)
    to restrict processing to, instead of every class folder under the
    month. Useful for uploading just a few classes without re-touching
    (and duplicating) everything else already uploaded."""
    if shutil.which("rclone") is None:
        raise common.AbleSignError("rclone not found. Install it first: brew install rclone")

    print(f"Looking for Drive month folder '{month}' under the Programming folder...")
    month_folders = common.rclone_list_subfolders(common.PARENT_DRIVE_FOLDER_ID)
    match = next((fid for name, fid in month_folders if name.strip().lower() == month.strip().lower()), None)
    if match is None:
        available = ", ".join(name for name, _ in month_folders)
        raise common.AbleSignError(f"No Drive subfolder named '{month}' found. Available: {available}")
    drive_month_id = match
    print(f"Found Drive folder '{month}' (id {drive_month_id})\n")

    class_folders = common.rclone_list_subfolders(drive_month_id)
    if not class_folders:
        raise common.AbleSignError(f"No class subfolders found under Drive folder '{month}'")

    if programs:
        wanted = {p.strip().lower() for p in programs}
        found_names = {name.strip().lower() for name, _fid in class_folders}
        missing = wanted - found_names
        if missing:
            raise common.AbleSignError(f"--programs named folder(s) not found under '{month}': {', '.join(sorted(missing))}")
        class_folders = [(name, fid) for name, fid in class_folders if name.strip().lower() in wanted]

    ablesign_root = f"GROUP FITNESS/{month}"
    ablesign_root_id = None if dry_run else common.resolve_or_create_path(ablesign_root)

    total = len(class_folders)
    uploaded_count = 0
    print(f"{total} class folder(s) to process.\n")

    for i, (class_name, drive_id) in enumerate(class_folders, start=1):
        print(f"[{i}/{total}] {class_name}")
        with tempfile.TemporaryDirectory() as tmpdir:
            common.rclone_pull_folder(drive_id, tmpdir)
            filenames = common.list_local_files(tmpdir)

            if not filenames:
                print("  EMPTY - no files at all in this Drive folder, skipping")
                continue

            tv_files = {}
            for name in filenames:
                tag = common.tv_tag(name)
                if tag:
                    tv_files[tag] = name
                else:
                    print(f"  WARNING: '{name}' has no TV1/TV3/TV5 tag, skipping this file")

            print(f"  files found: {tv_files}")

            if not tv_files:
                print("  MISSING all TV1/TV3/TV5 files (files present but none tagged), skipping")
                continue
            if dry_run:
                uploaded_count += len(tv_files)
                continue

            folder_id = common.get_or_create_folder(class_name, ablesign_root_id)[0]
            for tag, fname in tv_files.items():
                data, mimetype = common.read_file(tmpdir, fname)
                media_id = common.upload_media(fname, mimetype, data, folder_id)
                uploaded_count += 1
                print(f"  uploaded {fname} -> media_files id {media_id} (AbleSign folder {folder_id})")

    verb = "would upload" if dry_run else "uploaded"
    print(f"\nDone. {uploaded_count} file(s) {verb} across {total} class folder(s).")
    return uploaded_count


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--month", required=True,
        help='Month folder name, must match a subfolder under the Drive Programming '
             'folder exactly (case-insensitive), e.g. "8. August"',
    )
    parser.add_argument(
        "--programs",
        help="Comma-separated list of exact class-folder names to upload, instead of every "
             'class folder under the month, e.g. "ATH CON SPEED W12,ATH CON SPEED W34"',
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List what would be uploaded, touch nothing in AbleSign",
    )
    args = parser.parse_args()
    programs = [p.strip() for p in args.programs.split(",")] if args.programs else None
    run(args.month, args.dry_run, programs=programs)


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
