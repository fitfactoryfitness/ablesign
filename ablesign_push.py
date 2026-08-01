#!/usr/bin/env python3
"""
ablesign_push.py

Pulls a Drive folder down via rclone (remote name "gdrive", see setup below),
then pushes its file(s) to the matching AbleSign screen's playlist with a
fixed weekly display schedule.

Addresses the Drive folder by its FOLDER ID, not by name/path. This matters
because a lot of Fit Factory's Drive content is shared-with-you rather than
sitting in your own My Drive, and plain name-path lookups can't reliably
find those. IDs work regardless of ownership and don't break if a folder
gets renamed later.

To get a folder's ID: open it in Drive, the ID is the last segment of the
URL, e.g. https://drive.google.com/drive/folders/1-QJlITGPo-gvWflO8EKU5wamzSS0gMYg
                                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

One-time setup:
  brew install rclone
  rclone config    # name the remote "gdrive", pick Google Drive, use
                    # auto-config (opens a browser to log in). No GCP
                    # project needed, rclone has its own registered app.
  pip install requests

Usage:
  python3 ablesign_push.py --folder-id 1-QJlITGPo-gvWflO8EKU5wamzSS0gMYg \
      --screen-name "LOUNGE MAIN SCREEN" --day fri --start 09:00 --end 12:00

  # preview only, touches nothing in AbleSign:
  python3 ablesign_push.py --folder-id 1-QJlITGPo-gvWflO8EKU5wamzSS0gMYg \
      --screen-name "LOUNGE MAIN SCREEN" --day fri --start 09:00 --end 12:00 --dry-run
"""

import argparse
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile

import requests

# --------------------------------------------------------------------
# Config - the API key lives here per your instruction. Rotate it in
# AbleSign (Account > API Keys) if this file ever leaves your machine.
# --------------------------------------------------------------------
ABLESIGN_API_KEY = "ak_1c9d0575130dabc8d361567017896164eae8c52c"
ABLESIGN_BASE = "https://api.ablesign.tv/api/v1"
RCLONE_REMOTE = "gdrive"

DAY_ALIASES = {
    "mon": "mon", "monday": "mon",
    "tue": "tue", "tuesday": "tue",
    "wed": "wed", "wednesday": "wed",
    "thu": "thu", "thursday": "thu",
    "fri": "fri", "friday": "fri",
    "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}


# --------------------------------------------------------------------
# Drive (via rclone)
# --------------------------------------------------------------------

def pull_drive_folder(folder_id, dest_dir):
    if shutil.which("rclone") is None:
        sys.exit("rclone not found. Install it first: brew install rclone")
    # Address the folder by ID directly (works whether it's owned or
    # shared-with-you), instead of a fragile name-based path lookup.
    remote_spec = f"{RCLONE_REMOTE},root_folder_id={folder_id}:"
    result = subprocess.run(
        ["rclone", "copy", remote_spec, dest_dir],
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
    path = os.path.join(folder, name)
    with open(path, "rb") as fh:
        data = fh.read()
    mimetype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return data, mimetype


# --------------------------------------------------------------------
# AbleSign
# --------------------------------------------------------------------

def ablesign_headers():
    return {"Authorization": f"Bearer {ABLESIGN_API_KEY}"}


def get_screen_by_title(title):
    r = requests.get(
        f"{ABLESIGN_BASE}/screens",
        headers=ablesign_headers(),
        params={"title": title, "limit": 200},
        timeout=30,
    )
    r.raise_for_status()
    candidates = [
        s for s in r.json()["data"]
        if s["title"].strip().lower() == title.strip().lower()
    ]
    if not candidates:
        sys.exit(
            f"No AbleSign screen titled '{title}'. Check the exact screen "
            "name in AbleSign, it must match the Drive folder name exactly."
        )
    if len(candidates) > 1:
        sys.exit(
            f"Multiple AbleSign screens match '{title}'. Screen titles must "
            "be unique across your workspace for this to work safely."
        )
    return candidates[0]


def upload_media(filename, mimetype, data):
    r = requests.post(
        f"{ABLESIGN_BASE}/media_files/init_upload",
        headers=ablesign_headers(),
        json={"filename": filename, "mimeType": mimetype, "size": len(data)},
        timeout=30,
    )
    r.raise_for_status()
    init = r.json()["data"]

    put = requests.put(
        init["url"], data=data, headers={"Content-Type": mimetype}, timeout=120
    )
    put.raise_for_status()

    r2 = requests.post(
        f"{ABLESIGN_BASE}/media_files/finish_upload",
        headers=ablesign_headers(),
        json={"uploadId": init["uploadId"]},
        timeout=60,
    )
    r2.raise_for_status()
    return r2.json()["data"]["id"]


ALL_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def add_playlist_item(screen_id, media_id, day, start, end, duration):
    day_key = DAY_ALIASES[day.lower()]
    item = {
        "mediafileId": media_id,
        "displayDuration": duration,
        "scheduleEnabled": True,
    }
    # Explicitly zero out every other day. Leaving them unset makes AbleSign
    # default to 00:00-23:59 (shown all day), which collides with whatever
    # else is scheduled on this screen the rest of the week.
    for d in ALL_DAY_KEYS:
        if d == day_key:
            item[f"{d}Start"] = start
            item[f"{d}End"] = end
        else:
            item[f"{d}Start"] = "00:00"
            item[f"{d}End"] = "00:00"
    r = requests.post(
        f"{ABLESIGN_BASE}/screens/{screen_id}/playlist_items",
        headers=ablesign_headers(),
        json={"items": [item], "position": "end"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--folder-id", required=True,
        help="Drive folder ID (the last part of the folder's URL)",
    )
    parser.add_argument(
        "--screen-name", required=True,
        help="AbleSign screen title to push this content to",
    )
    parser.add_argument("--day", required=True, choices=sorted(DAY_ALIASES.keys()))
    parser.add_argument("--start", required=True, help="HH:MM, e.g. 09:00")
    parser.add_argument("--end", required=True, help="HH:MM, e.g. 12:00")
    parser.add_argument(
        "--duration", type=int, default=10, help="Display duration in seconds (default 10)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Pull from Drive and list files only, touch nothing in AbleSign",
    )
    args = parser.parse_args()

    screen_name = args.screen_name

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Pulling folder {args.folder_id} from Drive via rclone...")
        pull_drive_folder(args.folder_id, tmpdir)

        filenames = list_local_files(tmpdir)
        if not filenames:
            sys.exit(f"No files found in Drive folder {args.folder_id}")

        print(f"Target AbleSign screen (by name): {screen_name}")
        print(f"Schedule: {args.day} {args.start}-{args.end}, duration {args.duration}s")
        print(f"Files found: {filenames}")

        if args.dry_run:
            print("\nDry run only, stopping before any AbleSign calls.")
            return

        screen = get_screen_by_title(screen_name)
        print(f"Matched AbleSign screen id {screen['id']} ({screen['title']})")

        for name in filenames:
            print(f"Uploading {name}...")
            data, mimetype = read_file(tmpdir, name)
            media_id = upload_media(name, mimetype, data)
            print(f"  uploaded as media_files id {media_id}")
            add_playlist_item(screen["id"], media_id, args.day, args.start, args.end, args.duration)
            print(f"  added to playlist for {args.day} {args.start}-{args.end}")

    print("\nDone.")


if __name__ == "__main__":
    main()
