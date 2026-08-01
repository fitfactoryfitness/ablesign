#!/usr/bin/env python3
"""
ablesign_batch.py

Batch-pushes an entire month's slides from Drive to AbleSign in one run,
setting each screen's display schedule from the AI SCHEDULE tab, including
classes that need multiple entries (e.g. a class airing twice in one day
gets two separate playlist items on the same screen, same uploaded file).

Before running: export the "AI SCHEDULE" tab to CSV yourself (Google
Sheets: File > Download > Comma-separated values (.csv, current sheet))
and save it as schedule.csv next to this script. This sidesteps any
ambiguity about which tab a script would otherwise grab.

Setup (same as ablesign_push.py / ablesign_setup.py):
  brew install rclone && rclone config    (remote name "gdrive")
  pip install requests

Usage:
  python3 ablesign_batch.py \
      --drive-folder-id 1l_C_uoSo2Rkln2QsMlj85wKnEh92Jg__ \
      --ablesign-root "Claude/8. August" \
      --schedule-csv schedule.csv \
      --dry-run

Drop --dry-run to actually push everything for real.
"""

import argparse
import csv
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

import requests

ABLESIGN_API_KEY = "ak_1c9d0575130dabc8d361567017896164eae8c52c"
ABLESIGN_BASE = "https://api.ablesign.tv/api/v1"
RCLONE_REMOTE = "gdrive"

# TV tag in filename -> AbleSign screen id (all DRILLROOM)
SCREENS = {
    "TV1": 499083,
    "TV3": 499094,
    "TV5": 499095,
}

DURATION = 10  # seconds, matches your existing playlist convention

ALL_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_ALIASES = {
    "mon": "mon", "monday": "mon",
    "tue": "tue", "tuesday": "tue",
    "wed": "wed", "wednesday": "wed",
    "thu": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri",
    "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}


# ---------------------------------------------------------------------
# rclone / Drive
# ---------------------------------------------------------------------

def rclone_list_subfolders(folder_id):
    """Returns [(name, id), ...] for the direct child folders of folder_id."""
    result = subprocess.run(
        ["rclone", "lsjson", f"{RCLONE_REMOTE},root_folder_id={folder_id}:", "--dirs-only"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"rclone lsjson failed:\n{result.stderr}")
    import json as _json
    entries = _json.loads(result.stdout or "[]")
    return [(e["Name"], e["ID"]) for e in entries]


def rclone_pull_folder(folder_id, dest_dir):
    result = subprocess.run(
        ["rclone", "copy", f"{RCLONE_REMOTE},root_folder_id={folder_id}:", dest_dir],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"rclone copy failed:\n{result.stderr}")


def list_local_files(folder):
    return sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and not f.startswith(".")
    )


def read_file(folder, name):
    with open(os.path.join(folder, name), "rb") as fh:
        data = fh.read()
    mimetype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return data, mimetype


def tv_tag(filename):
    up = filename.upper()
    for tag in ("TV1", "TV3", "TV5"):
        # matches "TV1" as well as "TV 1" (space between TV and the digit)
        pattern = tag[:2] + r"\s*" + tag[2:]
        if re.search(pattern, up):
            return tag
    return None


# ---------------------------------------------------------------------
# AbleSign
# ---------------------------------------------------------------------

def ablesign_headers():
    return {"Authorization": f"Bearer {ABLESIGN_API_KEY}"}


def get_or_create_ablesign_folder(title, parent_id):
    r = requests.get(
        f"{ABLESIGN_BASE}/folders", headers=ablesign_headers(),
        params={"title": title, "limit": 200}, timeout=30,
    )
    r.raise_for_status()
    for f in r.json()["data"]:
        if f["title"].strip().lower() == title.strip().lower() and f.get("parentFolderId") == parent_id:
            return f["id"]
    r2 = requests.post(
        f"{ABLESIGN_BASE}/folders", headers=ablesign_headers(),
        json={"title": title, "parentFolderId": parent_id}, timeout=30,
    )
    r2.raise_for_status()
    return r2.json()["data"]["id"]


def resolve_ablesign_root(root_path):
    parent_id = None
    for segment in root_path.split("/"):
        parent_id = get_or_create_ablesign_folder(segment.strip(), parent_id)
    return parent_id


def upload_media(filename, mimetype, data, folder_id):
    r = requests.post(
        f"{ABLESIGN_BASE}/media_files/init_upload", headers=ablesign_headers(),
        json={"filename": filename, "mimeType": mimetype, "size": len(data), "folderId": folder_id},
        timeout=30,
    )
    r.raise_for_status()
    init = r.json()["data"]

    put = requests.put(init["url"], data=data, headers={"Content-Type": mimetype}, timeout=120)
    put.raise_for_status()

    r2 = requests.post(
        f"{ABLESIGN_BASE}/media_files/finish_upload", headers=ablesign_headers(),
        json={"uploadId": init["uploadId"]}, timeout=60,
    )
    r2.raise_for_status()
    return r2.json()["data"]["id"]


# AbleSign's docs list playlist writes (add/update/delete item) capped at 15/min and
# 30/hr, PER SCREEN. Both windows are enforced here, the 30/hr one is the real
# constraint for a full month's worth of items, not the 15/min one.
_PER_MIN_LIMIT = 13   # a little under 15 for margin
_PER_HOUR_LIMIT = 28  # a little under 30 for margin
_recent_calls = defaultdict(list)  # screen_id -> [timestamps]


def _throttle(screen_id):
    while True:
        now = time.time()
        calls = _recent_calls[screen_id]
        calls[:] = [t for t in calls if now - t < 3600]
        last_min = [t for t in calls if now - t < 60]
        if len(calls) < _PER_HOUR_LIMIT and len(last_min) < _PER_MIN_LIMIT:
            calls.append(now)
            return
        if len(calls) >= _PER_HOUR_LIMIT:
            wait = 3600 - (now - calls[0]) + 1
        else:
            wait = 60 - (now - last_min[0]) + 1
        print(f"    [screen {screen_id}] pacing under AbleSign's rate limit, sleeping {wait:.0f}s...")
        time.sleep(max(wait, 1))


def _playlist_write(method, url, screen_id, **kwargs):
    for attempt in range(6):
        _throttle(screen_id)
        r = requests.request(method, url, headers=ablesign_headers(), timeout=30, **kwargs)
        if r.status_code != 429:
            r.raise_for_status()
            return r
        wait = float(r.headers.get("Retry-After", 30))
        print(f"    [screen {screen_id}] got 429 anyway, waiting {wait:.0f}s and retrying (attempt {attempt + 1}/6)")
        time.sleep(wait)
    r.raise_for_status()
    return r


def add_playlist_item(screen_id, media_id, day, start, end, duration=DURATION):
    day_key = DAY_ALIASES[day.lower()]
    item = {"mediafileId": media_id, "displayDuration": duration, "scheduleEnabled": True}
    for d in ALL_DAY_KEYS:
        if d == day_key:
            item[f"{d}Start"] = start
            item[f"{d}End"] = end
        else:
            item[f"{d}Start"] = "00:00"
            item[f"{d}End"] = "00:00"
    r = _playlist_write(
        "POST", f"{ABLESIGN_BASE}/screens/{screen_id}/playlist_items", screen_id,
        json={"items": [item], "position": "end"},
    )
    return r.json()


def list_playlist_items(screen_id):
    # NOTE: unverified against real AbleSign docs, guessed from the pattern every
    # other list endpoint in this API follows (folders, screens, media_files).
    r = requests.get(f"{ABLESIGN_BASE}/screens/{screen_id}/playlist_items", headers=ablesign_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["data"]


def delete_playlist_item(screen_id, item_id):
    # NOTE: unverified, same caveat as above.
    _playlist_write("DELETE", f"{ABLESIGN_BASE}/screens/{screen_id}/playlist_items/{item_id}", screen_id)


def clear_playlist(screen_id):
    items = list_playlist_items(screen_id)
    if not items:
        print(f"  screen {screen_id}: playlist already empty")
        return
    print(f"  screen {screen_id}: deleting {len(items)} existing playlist item(s)")
    for item in items:
        delete_playlist_item(screen_id, item["id"])


# ---------------------------------------------------------------------
# schedule.csv
# ---------------------------------------------------------------------

def normalize_time(t):
    hh, mm = t.strip().split(":")
    return f"{int(hh):02d}:{int(mm):02d}"


def load_schedule(path):
    if not os.path.exists(path):
        sys.exit(
            f"Schedule file not found: {path}\n"
            "Export the AI SCHEDULE tab first: Google Sheets > File > Download "
            "> Comma-separated values (.csv, current sheet), save as this filename."
        )
    schedule = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cls = row["Class"].strip()
            day = row["Day"].strip()
            start = normalize_time(row["Start"])
            end = normalize_time(row["End"])
            schedule.setdefault(cls.lower(), []).append((day, start, end))
    return schedule


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--drive-folder-id", required=True, help="Drive ID of the month folder")
    parser.add_argument("--ablesign-root", required=True, help='e.g. "Claude/8. August"')
    parser.add_argument("--schedule-csv", required=True, help="Local CSV exported from AI SCHEDULE")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List what would happen, pull nothing from Drive beyond folder names, touch nothing in AbleSign",
    )
    parser.add_argument(
        "--test-screen-id", type=int, default=None,
        help="Redirect every TV1/TV3/TV5 file to this single screen id instead of the real DRILLROOM "
             "screens, for end-to-end testing on a throwaway screen (e.g. Headquarter).",
    )
    parser.add_argument(
        "--clear-playlists-first", action="store_true",
        help="Delete every existing playlist item on the target screen(s) before pushing new content. "
             "UNVERIFIED: the list/delete endpoints this calls are guessed, never confirmed against "
             "AbleSign's docs. Test this on Headquarter before trusting it on real screens. "
             "Requires --yes-really-clear.",
    )
    parser.add_argument(
        "--yes-really-clear", action="store_true",
        help="Required alongside --clear-playlists-first, confirms you mean it",
    )
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        sys.exit("rclone not found. Install it first: brew install rclone")

    active_screens = SCREENS
    if args.test_screen_id is not None:
        active_screens = {tag: args.test_screen_id for tag in SCREENS}
        print(f"TEST MODE: every TV1/TV3/TV5 file will be pushed to screen id {args.test_screen_id} instead "
              f"of the real DRILLROOM screens {list(SCREENS.values())}.\n")

    if args.clear_playlists_first:
        target_ids = sorted(set(active_screens.values()))
        if args.dry_run:
            print(f"Would clear playlists on screen(s): {target_ids}\n")
        else:
            if not args.yes_really_clear:
                sys.exit("--clear-playlists-first also requires --yes-really-clear, refusing to guess that you meant it")
            print(f"Clearing playlists on screen(s): {target_ids}")
            for sid in target_ids:
                clear_playlist(sid)
            print()

    schedule = load_schedule(args.schedule_csv)
    class_folders = rclone_list_subfolders(args.drive_folder_id)

    if not class_folders:
        sys.exit(f"No subfolders found in Drive folder {args.drive_folder_id}")

    ablesign_root_id = None if args.dry_run else resolve_ablesign_root(args.ablesign_root)

    for class_name, drive_id in class_folders:
        key = class_name.strip().lower()
        rows = schedule.get(key)
        if not rows:
            print(f"SKIP '{class_name}': no matching rows in {args.schedule_csv} (name mismatch?)")
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            rclone_pull_folder(drive_id, tmpdir)
            filenames = list_local_files(tmpdir)

            tv_files = {}
            for name in filenames:
                tag = tv_tag(name)
                if tag:
                    tv_files[tag] = name
                else:
                    print(f"  WARNING: '{name}' in '{class_name}' has no TV1/TV3/TV5 tag, skipping this file")

            print(f"\n{class_name}: {len(rows)} schedule slot(s), files found: {tv_files}")

            if args.dry_run:
                for day, start, end in rows:
                    print(f"  would schedule {day} {start}-{end}")
                continue

            folder_id = get_or_create_ablesign_folder(class_name, ablesign_root_id)

            for tag, screen_id in active_screens.items():
                fname = tv_files.get(tag)
                if not fname:
                    print(f"  MISSING {tag} file for '{class_name}', skipping this screen")
                    continue
                data, mimetype = read_file(tmpdir, fname)
                media_id = upload_media(fname, mimetype, data, folder_id)
                print(f"  uploaded {fname} -> media_files id {media_id} (AbleSign folder {folder_id})")
                for day, start, end in rows:
                    add_playlist_item(screen_id, media_id, day, start, end)
                    print(f"    added to screen {screen_id} ({tag}) for {day} {start}-{end}")

    print("\nDone.")


if __name__ == "__main__":
    main()
