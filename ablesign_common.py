#!/usr/bin/env python3
"""
ablesign_common.py

Shared helpers for upload_content.py, delete_playlist.py, create_playlist.py.
Not meant to be run directly.

Endpoint shapes below were confirmed against the live docs at
https://apidocs.ablesign.tv/ on 2026-07-31. Two corrections vs the older
ablesign_batch.py / ablesign_setup.py scripts in this folder, which guessed
wrong:
  - There is NO "DELETE /screens/{id}/playlist_items/{itemId}" endpoint.
    Clearing a playlist means PUT /screens/{id}/playlist with items: [].
  - The list endpoint for a screen's playlist is GET /screens/{id}/playlist
    (returns {"data": {"items": [...], ...other playlist settings}}), not
    GET /screens/{id}/playlist_items.

Deliberately NOT implemented: AbleSign's periodicScheduleEnabled /
scheduleStartDate / scheduleEndDate / scheduleRrule fields on playlist
items (date-bounded scheduling, e.g. "only weeks 1-2 of August"). Per
Lucas's instruction, schedule.csv only has Class/Day/Start/End columns —
every row becomes a plain weekly recurring playlist item for the whole
month. Date-bounded swaps (like a WEEKS 1-2 vs WEEKS 3-4 class, or a
one-off holiday special) are handled by hand in the AbleSign UI.
"""

import csv
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests


class AbleSignError(Exception):
    """Raised for any expected/user-facing error (missing config, screen not
    found, etc). Never sys.exit() from this module: it's imported both by
    one-shot CLI scripts AND by the long-running web app backend, where
    sys.exit() would raise SystemExit inside a request-handling thread and
    just hang that request instead of returning a clean error. CLI scripts
    catch AbleSignError in their own main() and exit(1) there; the backend
    catches it and returns a proper JSON error."""


_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ablesign_api_key")


def _load_api_key():
    env_key = os.environ.get("ABLESIGN_API_KEY")
    if env_key:
        return env_key.strip()
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE) as f:
            key = f.read().strip()
        if key:
            return key
    raise AbleSignError(
        "No AbleSign API key configured. Either set the ABLESIGN_API_KEY environment "
        f"variable, or create a file at {_KEY_FILE} containing just the key "
        "(see .ablesign_api_key.example). Ask Lucas for the current key."
    )


ABLESIGN_API_KEY = _load_api_key()
ABLESIGN_BASE = "https://api.ablesign.tv/api/v1"
RCLONE_REMOTE = "gdrive"

# Drive "Programming" root folder, parent of every month folder (8. August, etc).
# https://drive.google.com/drive/folders/1sm9n_jKbWJEkBd-ziiyBTrvjbwJyK-ye
PARENT_DRIVE_FOLDER_ID = "1sm9n_jKbWJEkBd-ziiyBTrvjbwJyK-ye"

# TV tag in filename -> AbleSign screen id (all DRILLROOM), loaded from screens.json
_SCREENS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screens.json")


def load_screens():
    import json
    with open(_SCREENS_JSON) as f:
        return json.load(f)


# Headquarter TV, used for test runs before trusting the real DRILLROOM screens.
# Not in screens.json since it's not part of the TV1/TV3/TV5 rotation.
HEADQUARTER_SCREEN_ID = 498279
HEADQUARTER_SCREEN_NAME = "Headquarter"

DURATION = 10  # seconds, matches existing playlist convention

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
        raise AbleSignError(f"rclone lsjson failed:\n{result.stderr}")
    import json as _json
    entries = _json.loads(result.stdout or "[]")
    return [(e["Name"], e["ID"]) for e in entries]


def rclone_pull_folder(folder_id, dest_dir):
    result = subprocess.run(
        ["rclone", "copy", f"{RCLONE_REMOTE},root_folder_id={folder_id}:", dest_dir],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AbleSignError(f"rclone copy failed:\n{result.stderr}")


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
# AbleSign: auth / screens
# ---------------------------------------------------------------------

def ablesign_headers():
    return {"Authorization": f"Bearer {ABLESIGN_API_KEY}"}


def list_screens():
    """Returns [{"id":..., "title":...}, ...] for every screen in the
    AbleSign account. Used by the web app's screen dropdowns."""
    r = requests.get(f"{ABLESIGN_BASE}/screens", headers=ablesign_headers(), params={"limit": 200}, timeout=30)
    r.raise_for_status()
    return [{"id": s["id"], "title": s["title"]} for s in r.json()["data"]]


def get_screen_by_id(screen_id):
    r = requests.get(f"{ABLESIGN_BASE}/screens/{screen_id}", headers=ablesign_headers(), timeout=30)
    if r.status_code == 404:
        raise AbleSignError(f"No AbleSign screen with id {screen_id}.")
    r.raise_for_status()
    return r.json()["data"]


def get_screen_by_title(title):
    r = requests.get(
        f"{ABLESIGN_BASE}/screens", headers=ablesign_headers(),
        params={"title": title, "limit": 200}, timeout=30,
    )
    r.raise_for_status()
    candidates = [
        s for s in r.json()["data"]
        if s["title"].strip().lower() == title.strip().lower()
    ]
    if not candidates:
        raise AbleSignError(
            f"No AbleSign screen titled '{title}'. Check the exact screen name in AbleSign."
        )
    if len(candidates) > 1:
        raise AbleSignError(
            f"Multiple AbleSign screens match '{title}'. Screen titles must be unique "
            "across your workspace for this to work safely; use --screen-id instead."
        )
    return candidates[0]


def resolve_screen(screen_id, screen_name):
    """One of screen_id/screen_name must be set (argparse mutually-exclusive
    required group enforces this upstream). Returns the full screen dict."""
    if screen_id is not None:
        return get_screen_by_id(screen_id)
    return get_screen_by_title(screen_name)


def tag_for_screen(screen_id):
    """Reverse-lookup screens.json: which TV tag (if any) is this screen id?"""
    for tag, sid in load_screens().items():
        if sid == screen_id:
            return tag
    return None


# ---------------------------------------------------------------------
# AbleSign: folders
# ---------------------------------------------------------------------

def list_child_folders(parent_id):
    """Returns [(title, id), ...] for the direct children of parent_id
    (parent_id=None means top-level folders)."""
    params = {"limit": 200}
    if parent_id is not None:
        params["folderId"] = parent_id
    r = requests.get(f"{ABLESIGN_BASE}/folders", headers=ablesign_headers(), params=params, timeout=30)
    r.raise_for_status()
    # Belt-and-suspenders: also filter client-side on parentFolderId, in case
    # the folderId query param doesn't scope server-side the way we expect.
    return [(f["title"], f["id"]) for f in r.json()["data"] if f.get("parentFolderId") == parent_id]


def get_or_create_folder(title, parent_id=None):
    for existing_title, existing_id in list_child_folders(parent_id):
        if existing_title.strip().lower() == title.strip().lower():
            return existing_id, False
    r2 = requests.post(
        f"{ABLESIGN_BASE}/folders", headers=ablesign_headers(),
        json={"title": title, "parentFolderId": parent_id}, timeout=30,
    )
    r2.raise_for_status()
    return r2.json()["data"]["id"], True


def resolve_or_create_path(root_path):
    """root_path like 'Claude/8. August'. Creates any missing segment."""
    parent_id = None
    for segment in root_path.split("/"):
        parent_id, _created = get_or_create_folder(segment.strip(), parent_id)
    return parent_id


def lookup_path(root_path):
    """Same as resolve_or_create_path but read-only: exits with an error if
    any segment doesn't already exist, instead of creating it. Used by
    create_playlist.py, which expects upload_content.py to have run first."""
    parent_id = None
    for segment in root_path.split("/"):
        segment = segment.strip()
        match = None
        for existing_title, existing_id in list_child_folders(parent_id):
            if existing_title.strip().lower() == segment.lower():
                match = existing_id
                break
        if match is None:
            raise AbleSignError(
                f"AbleSign folder '{segment}' not found under '{root_path}' "
                f"(while resolving '{root_path}'). Run Upload Content for this month first."
            )
        parent_id = match
    return parent_id


# ---------------------------------------------------------------------
# AbleSign: media files
# ---------------------------------------------------------------------

def list_media_files(folder_id):
    """Returns [(name, id), ...] for media files directly inside folder_id.
    name is originalFilename (falls back to title) so tv_tag() can match it.

    NOTE: the docs say each item has a "folderId" field, but in practice the
    live API returns it as null on every item in this list response (even
    though the "folderId" query param IS correctly scoping the results
    server-side, confirmed against the real API on 2026-07-31). So unlike
    list_child_folders(), there's no reliable field to double-check
    client-side here - we just trust the query param."""
    r = requests.get(
        f"{ABLESIGN_BASE}/media_files", headers=ablesign_headers(),
        params={"folderId": folder_id, "limit": 200}, timeout=30,
    )
    r.raise_for_status()
    out = []
    for m in r.json()["data"]:
        name = m.get("originalFilename") or m.get("title")
        out.append((name, m["id"]))
    return out


def get_media_file(media_id):
    r = requests.get(f"{ABLESIGN_BASE}/media_files/{media_id}", headers=ablesign_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["data"]


def delete_media_file(media_id):
    """Per the docs: 'Deletes the file and removes it from all playlists' -
    if this media is currently scheduled anywhere, it goes dark immediately.
    Permanent, no undo."""
    r = requests.delete(f"{ABLESIGN_BASE}/media_files/{media_id}", headers=ablesign_headers(), timeout=30)
    r.raise_for_status()


def delete_folder(folder_id):
    """Only safe to call once the folder is already empty - see
    delete_folder_tree(), which guarantees that by deleting bottom-up."""
    r = requests.delete(f"{ABLESIGN_BASE}/folders/{folder_id}", headers=ablesign_headers(), timeout=30)
    r.raise_for_status()


def all_live_media_ids():
    """Every mediafileId currently referenced in any screen's playlist,
    across every screen in the account (not just TV1/TV3/TV5) - used to
    avoid deleting a file that's actively live somewhere right now."""
    ids = set()
    for screen in list_screens():
        playlist = get_playlist(screen["id"])
        for item in playlist.get("items", []):
            mid = item.get("mediafileId")
            if mid is not None:
                ids.add(mid)
    return ids


def delete_folder_tree(folder_id, dry_run=False, indent=""):
    """Recursively deletes every media file and subfolder under folder_id,
    then folder_id itself - files first, subfolders depth-first, the
    folder last, so nothing is ever deleted while still non-empty
    regardless of whatever AbleSign's own cascade behavior turns out to
    be (undocumented). Returns (files_deleted, folders_deleted).

    Anything (folder or file) with "psc" anywhere in its name (case
    insensitive) is skipped entirely - not deleted, not recursed into -
    as a blanket safety net for PSC content regardless of where it turns
    up in the tree. A skip anywhere in a subtree propagates up: a folder
    that still contains protected content (even nested several levels
    down) is left in place rather than deleted, since deleting it would
    orphan whatever's still inside it.

    Returns (files_deleted, folders_deleted, anything_skipped)."""
    files_deleted = 0
    folders_deleted = 0
    anything_skipped = False

    for name, child_id in list_child_folders(folder_id):
        if "psc" in name.lower():
            print(f"{indent}  SKIPPING folder '{name}' (protected: contains \"PSC\")")
            anything_skipped = True
            continue
        f, d, child_skipped = delete_folder_tree(child_id, dry_run, indent + "  ")
        files_deleted += f
        folders_deleted += d
        anything_skipped = anything_skipped or child_skipped

    for name, media_id in list_media_files(folder_id):
        if "psc" in name.lower():
            print(f"{indent}  SKIPPING file '{name}' (protected: contains \"PSC\")")
            anything_skipped = True
            continue
        verb = "would delete" if dry_run else "deleting"
        print(f"{indent}  {verb} file: {name}")
        if not dry_run:
            delete_media_file(media_id)
        files_deleted += 1

    if anything_skipped:
        # Leave this folder in place - it (or a descendant, however deep)
        # still holds protected content, so deleting it would orphan that
        # content instead of just leaving it accessible where it already was.
        print(f"{indent}NOT deleting folder (id {folder_id}) - still contains protected PSC content")
        return files_deleted, folders_deleted, True

    verb = "would delete" if dry_run else "deleting"
    print(f"{indent}{verb} folder (id {folder_id})")
    if not dry_run:
        delete_folder(folder_id)
    folders_deleted += 1

    return files_deleted, folders_deleted, False


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


# ---------------------------------------------------------------------
# AbleSign: playlist (rate-limited: 15/min & 30/hr per screen per the docs)
# ---------------------------------------------------------------------

RATE_LIMIT_PER_MIN = 13   # a little under AbleSign's 15/min for margin
RATE_LIMIT_PER_HOUR = 28  # a little under AbleSign's 30/hr for margin
_recent_calls = defaultdict(list)  # screen_id -> [timestamps]


def _throttle(screen_id):
    while True:
        now = time.time()
        calls = _recent_calls[screen_id]
        calls[:] = [t for t in calls if now - t < 3600]
        last_min = [t for t in calls if now - t < 60]
        if len(calls) < RATE_LIMIT_PER_HOUR and len(last_min) < RATE_LIMIT_PER_MIN:
            calls.append(now)
            return
        if len(calls) >= RATE_LIMIT_PER_HOUR:
            wait = 3600 - (now - calls[0]) + 1
        else:
            wait = 60 - (now - last_min[0]) + 1
        print(f"    [screen {screen_id}] pacing under AbleSign's rate limit, sleeping {wait:.0f}s...")
        time.sleep(max(wait, 1))


def _playlist_write(method, url, screen_id, **kwargs):
    r = None
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


def get_playlist(screen_id):
    r = requests.get(f"{ABLESIGN_BASE}/screens/{screen_id}/playlist", headers=ablesign_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["data"]


def parse_iso(dt_str):
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def current_day_and_time():
    """('mon'..'sun', 'HH:MM') from this machine's local clock."""
    now = datetime.now()
    return ALL_DAY_KEYS[now.weekday()], now.strftime("%H:%M")


def get_playlist_rows(screen_id):
    """Returns a list of dicts, one per (item, active-day) combination:
    {day, start, end, title, item_id, media_id, duration, periodic_ok,
    period_start, period_end}. day/start/end are None for an item with no
    active day at all. periodic_ok reflects whether TODAY falls inside a
    manually-set periodicScheduleEnabled date range (see list_playlist.py);
    period_start/period_end are that range's dates (ISO, or None if the
    item isn't periodic). Shared by list_playlist.py and the web app."""
    playlist = get_playlist(screen_id)
    items = playlist.get("items", [])
    media_cache = {}
    now_utc = datetime.now(timezone.utc)
    rows = []

    for item in items:
        media_id = item.get("mediafileId")
        if media_id not in media_cache:
            try:
                media_cache[media_id] = get_media_file(media_id)
            except Exception:
                media_cache[media_id] = None
        media = media_cache[media_id]
        title = (media.get("originalFilename") or media.get("title")) if media else f"(media id {media_id}, lookup failed)"

        periodic_ok = True
        period_start = None
        period_end = None
        if item.get("periodicScheduleEnabled"):
            start_dt = parse_iso(item["scheduleStartDate"]) if item.get("scheduleStartDate") else None
            end_dt = parse_iso(item["scheduleEndDate"]) if item.get("scheduleEndDate") else None
            if start_dt and now_utc < start_dt:
                periodic_ok = False
            if end_dt and now_utc > end_dt:
                periodic_ok = False
            period_start = start_dt.date().isoformat() if start_dt else None
            period_end = end_dt.date().isoformat() if end_dt else None

        active_days = []
        for day in ALL_DAY_KEYS:
            start = (item.get(f"{day}Start") or "00:00:00")[:5]
            end = (item.get(f"{day}End") or "00:00:00")[:5]
            if not (start == "00:00" and end == "00:00"):
                active_days.append((day, start, end))

        base = {
            "title": title, "item_id": item.get("id"), "media_id": media_id,
            "duration": item.get("displayDuration"),
            "periodic_ok": periodic_ok, "period_start": period_start, "period_end": period_end,
        }
        if not active_days:
            rows.append({**base, "day": None, "start": None, "end": None})
        else:
            for day, start, end in active_days:
                rows.append({**base, "day": day, "start": start, "end": end})

    return rows


def is_row_live_now(row, current_day, current_time):
    return (
        row["periodic_ok"]
        and row["day"] == current_day
        and row["start"] is not None
        and row["start"] <= current_time < row["end"]
    )


def existing_playlist_signatures(screen_id):
    """Returns a set of (mediafileId, day_key, 'HH:MM', 'HH:MM') for every
    active day-window already on the screen's playlist. create_playlist.py
    checks a row against this set before adding it, so relaunching after an
    interruption (rate-limit pause, crash, closed terminal, ...) resumes
    cleanly instead of creating duplicate items. GET calls don't count
    against the playlist-writes rate limit, so this is a single cheap call
    up front, not per-item."""
    playlist = get_playlist(screen_id)
    sigs = set()
    for item in playlist.get("items", []):
        media_id = item.get("mediafileId")
        for day in ALL_DAY_KEYS:
            start = (item.get(f"{day}Start") or "00:00:00")[:5]
            end = (item.get(f"{day}End") or "00:00:00")[:5]
            if start == "00:00" and end == "00:00":
                continue
            sigs.add((media_id, day, start, end))
    return sigs


def clear_playlist(screen_id):
    """Replaces the screen's playlist with an empty item list, preserving
    the playlist's other settings (shuffle, transitions, ...)."""
    playlist = get_playlist(screen_id)
    item_count = len(playlist.get("items", []))
    if item_count == 0:
        print(f"  screen {screen_id}: playlist already empty")
        return
    body = {
        "shufflePlay": playlist.get("shufflePlay", False),
        "defaultTransition": playlist.get("defaultTransition"),
        "defaultTransitionSpeedLabel": playlist.get("defaultTransitionSpeedLabel"),
        "enableImageTransitions": playlist.get("enableImageTransitions", False),
        "enableWebappTransitions": playlist.get("enableWebappTransitions", False),
        "items": [],
    }
    print(f"  screen {screen_id}: clearing {item_count} existing playlist item(s)")
    _playlist_write("PUT", f"{ABLESIGN_BASE}/screens/{screen_id}/playlist", screen_id, json=body)


def _item_for_put(item):
    """Reconstructs a GET-shaped playlist item into the PUT request shape.
    PUT replaces the WHOLE playlist, so anything not carried over here -
    including a manually-set periodicScheduleEnabled/scheduleStartDate/
    scheduleEndDate on some OTHER unrelated item - would be silently
    destroyed. GET returns "HH:mm:ss" for day windows; PUT expects
    "HH:mm", hence the [:5] truncation."""
    out = {
        "mediafileId": item.get("mediafileId"),
        "webAppId": item.get("webAppId"),
        "displayDuration": item.get("displayDuration"),
        "sequenceNumber": item.get("sequenceNumber"),
        "transition": item.get("transition"),
        "transitionSpeedLabel": item.get("transitionSpeedLabel"),
        "scheduleEnabled": item.get("scheduleEnabled"),
        "scheduleStartDate": item.get("scheduleStartDate"),
        "scheduleEndDate": item.get("scheduleEndDate"),
        "scheduleRrule": item.get("scheduleRrule"),
        "periodicScheduleEnabled": item.get("periodicScheduleEnabled"),
    }
    for day in ALL_DAY_KEYS:
        out[f"{day}Start"] = (item.get(f"{day}Start") or "00:00:00")[:5]
        out[f"{day}End"] = (item.get(f"{day}End") or "00:00:00")[:5]
    return out


def remove_playlist_items(screen_id, media_ids_to_remove):
    """Removes just the items whose mediafileId is in media_ids_to_remove
    from a screen's playlist - everything else (including other items'
    manually-set periodic scheduling) is preserved exactly. Used by
    update_program.py to swap out one class's old slides without
    disturbing anything else on the screen. Returns how many were removed."""
    playlist = get_playlist(screen_id)
    items = playlist.get("items", [])
    keep = [it for it in items if it.get("mediafileId") not in media_ids_to_remove]
    removed_count = len(items) - len(keep)
    if removed_count == 0:
        return 0
    body = {
        "shufflePlay": playlist.get("shufflePlay", False),
        "defaultTransition": playlist.get("defaultTransition"),
        "defaultTransitionSpeedLabel": playlist.get("defaultTransitionSpeedLabel"),
        "enableImageTransitions": playlist.get("enableImageTransitions", False),
        "enableWebappTransitions": playlist.get("enableWebappTransitions", False),
        "items": [_item_for_put(it) for it in keep],
    }
    _playlist_write("PUT", f"{ABLESIGN_BASE}/screens/{screen_id}/playlist", screen_id, json=body)
    return removed_count


# ---------------------------------------------------------------------
# schedule.csv (Class,Day,Start,End) - see module docstring: no date-bounded
# periodic scheduling, every row becomes a plain weekly-recurring item.
# ---------------------------------------------------------------------

def normalize_time(t):
    hh, mm = t.strip().split(":")
    return f"{int(hh):02d}:{int(mm):02d}"


def load_schedule(path):
    if not os.path.exists(path):
        raise AbleSignError(
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


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_schedule_rows(path):
    """Returns an ordered list of {"class","day","start","end"} dicts,
    preserving original class-name casing and CSV row order. Used by the
    web app's schedule editor (load_schedule() above groups/lowercases
    instead, which is what the CLI scripts need for matching)."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "class": row["Class"].strip(),
                "day": row["Day"].strip(),
                "start": normalize_time(row["Start"]),
                "end": normalize_time(row["End"]),
            })
    return rows


def save_schedule_rows(path, rows):
    """Overwrites schedule.csv from a list of {"class","day","start","end"}
    dicts, keeping a timestamped backup of whatever was there before."""
    if os.path.exists(path):
        shutil.copyfile(path, f"{path}.bak-{int(time.time())}")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Class", "Day", "Start", "End"])
        for r in rows:
            writer.writerow([r["class"].strip(), r["day"].strip(), normalize_time(r["start"]), normalize_time(r["end"])])
