#!/usr/bin/env python3
"""
delete_ablesign_folders.py

Permanently deletes one or more top-level AbleSign folders (every
subfolder and media file inside them, recursively), and/or every loose
media file sitting at the account root, and/or clears TV1/TV3/TV5's
playlists - meant for wiping AbleSign down to a clean base before
switching to a new content package. No undo - AbleSign has no trash.

Safety:
  - Anything (folder or file, anywhere in the tree) with "psc" in its name
    (case insensitive) is never touched, and a folder that still contains
    protected PSC content afterward is left in place rather than deleted.
  - Any media file currently referenced by ANY screen's live playlist
    (checked account-wide, not just TV1/TV3/TV5) is automatically excluded
    from root-file deletion and reported separately, unless you pass
    --include-live. Deleting a live file immediately removes it from
    whatever playlist it's on (per AbleSign's own docs).

Usage:
  python3 delete_ablesign_folders.py --folders "2026,Claude,NEW DT PROGRAMMING" --root-files --clear-tvs --dry-run
  python3 delete_ablesign_folders.py --folders "2026,Claude,NEW DT PROGRAMMING" --root-files --clear-tvs --yes
"""

import argparse
import sys

import ablesign_common as common


def run(folder_names, include_root_files, clear_tvs, dry_run, include_live):
    top_folders = {name.strip().lower(): (name, fid) for name, fid in common.list_child_folders(None)}

    targets = []
    for name in folder_names:
        if "psc" in name.lower():
            raise common.AbleSignError(f"Refusing: '{name}' contains \"PSC\" and is protected.")
        match = top_folders.get(name.strip().lower())
        if match is None:
            raise common.AbleSignError(f"No top-level AbleSign folder named '{name}'.")
        targets.append(match)

    live_ids = common.all_live_media_ids() if (include_root_files and not include_live) else set()

    root_to_delete = []
    root_excluded_live = []
    root_excluded_psc = []
    if include_root_files:
        for name, media_id in common.list_media_files(None):
            if "psc" in name.lower():
                root_excluded_psc.append((name, media_id))
            elif media_id in live_ids:
                root_excluded_live.append((name, media_id))
            else:
                root_to_delete.append((name, media_id))

    print("=== Plan ===")
    for name, fid in targets:
        children = common.list_child_folders(fid)
        files = common.list_media_files(fid)
        print(f"  Folder '{name}' (id {fid}): {len(children)} subfolder(s), {len(files)} file(s) directly in it (deletes everything inside, recursively; skips anything PSC)")
    if include_root_files:
        print(f"  {len(root_to_delete)} root-level file(s) to delete")
        if root_excluded_psc:
            print(f"  {len(root_excluded_psc)} root-level file(s) EXCLUDED (protected: contains \"PSC\"):")
            for name, media_id in root_excluded_psc:
                print(f"    - {name} (id {media_id})")
        if root_excluded_live:
            print(f"  {len(root_excluded_live)} root-level file(s) EXCLUDED (currently live on a screen):")
            for name, media_id in root_excluded_live:
                print(f"    - {name} (id {media_id})")
    if clear_tvs:
        screens = common.load_screens()  # {"TV1": id, "TV3": id, "TV5": id}
        print(f"  Clear playlist on: {', '.join(f'{tag} (id {sid})' for tag, sid in screens.items())}")
    print()

    if dry_run:
        print("--- Dry run: showing exactly what would be deleted ---\n")
        total_files = 0
        total_folders = 0
        for name, fid in targets:
            print(f"[{name}]")
            f, d, _skipped = common.delete_folder_tree(fid, dry_run=True)
            total_files += f
            total_folders += d
            print()
        if include_root_files:
            print("[root files]")
            for name, media_id in root_to_delete:
                print(f"  would delete file: {name}")
            total_files += len(root_to_delete)
            print()
        if clear_tvs:
            print("[TV playlists]")
            for tag, screen_id in common.load_screens().items():
                playlist = common.get_playlist(screen_id)
                print(f"  would clear {tag} (id {screen_id}): {len(playlist.get('items', []))} item(s)")
        print(f"\nWould delete {total_files} file(s) and {total_folders} folder(s) total. Nothing was actually touched.")
        return

    print("--- Deleting for real ---\n")
    total_files = 0
    total_folders = 0
    for name, fid in targets:
        print(f"[{name}]")
        f, d, _skipped = common.delete_folder_tree(fid, dry_run=False)
        total_files += f
        total_folders += d
        print()
    if include_root_files:
        print("[root files]")
        for name, media_id in root_to_delete:
            print(f"  deleting file: {name}")
            common.delete_media_file(media_id)
        total_files += len(root_to_delete)
        print()
    if clear_tvs:
        print("[TV playlists]")
        for tag, screen_id in common.load_screens().items():
            print(f"  {tag} (id {screen_id}):")
            common.clear_playlist(screen_id)

    print(f"\nDone. Deleted {total_files} file(s) and {total_folders} folder(s).")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--folders", default="",
        help='Comma-separated top-level AbleSign folder names to delete entirely, e.g. "2026,Claude,NEW DT PROGRAMMING"',
    )
    parser.add_argument(
        "--root-files", action="store_true",
        help="Also delete every loose media file sitting at the account root",
    )
    parser.add_argument(
        "--clear-tvs", action="store_true",
        help="Also clear TV1/TV3/TV5's playlists entirely",
    )
    parser.add_argument(
        "--include-live", action="store_true",
        help="Also delete root files that are currently live on a screen (dangerous - "
             "immediately removes them from whatever's playing). Off by default.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show exactly what would be deleted, touch nothing",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Required to actually delete (without --dry-run), confirms you mean it",
    )
    args = parser.parse_args()

    folder_names = [f.strip() for f in args.folders.split(",") if f.strip()]
    if not folder_names and not args.root_files and not args.clear_tvs:
        parser.error("nothing to do - pass --folders, --root-files, and/or --clear-tvs")

    if not args.dry_run and not args.yes:
        parser.error("--yes is required to actually delete (or pass --dry-run to preview)")

    run(folder_names, args.root_files, args.clear_tvs, args.dry_run, args.include_live)


if __name__ == "__main__":
    try:
        main()
    except common.AbleSignError as e:
        sys.exit(str(e))
