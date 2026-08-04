#!/usr/bin/env python3
"""
webapp/backend/main.py

FastAPI backend for the AbleSign Control Panel. Thin wrapper around the
existing CLI scripts (ablesign_common.py, create_playlist.py,
upload_content.py) one directory up - imports and calls them directly, no
logic is duplicated here.

Fast read/write actions (screens, schedule, playlist viewing, delete) run
synchronously and return straight away. The two genuinely long actions
(upload content, create playlist for real) run as a background "job":
POST .../execute returns a job_id immediately, and the frontend polls
GET /api/jobs/{job_id} for the live log + status. Only one job runs at a
time - starting a second one while one is active returns 409, so two
big pushes can never collide or interleave their logs.

Run with: uvicorn main:app --reload --port 8000   (see webapp/package.json)
"""

import contextlib
import io
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ablesign_common.py / create_playlist.py / upload_content.py live two
# directories up from this file (webapp/backend/main.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import ablesign_common as common  # noqa: E402
import create_playlist  # noqa: E402
import upload_content  # noqa: E402

SCHEDULE_CSV = str(REPO_ROOT / "schedule.csv")

app = FastAPI(title="AbleSign Control Panel")
app.add_middleware(
    CORSMiddleware,
    # Everyone runs the frontend and backend together on their own laptop
    # (via start_app.sh), so this only ever needs to allow the local Vite
    # dev server talking to the local backend - never a remote origin.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(common.AbleSignError)
async def ablesign_error_handler(request: Request, exc: common.AbleSignError):
    """AbleSignError is raised for expected, user-facing problems (missing
    config, screen/folder not found, rclone missing, ...). Without this
    handler FastAPI would return a generic 500 with no useful message."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------------
# Background job manager - only one job (upload or create-playlist
# execute) runs at a time; each streams its print() output into a log
# string the frontend polls.
# ---------------------------------------------------------------------

_jobs_lock = threading.Lock()
_jobs = {}
_current_job_id = None


class _LiveLog(io.TextIOBase):
    def __init__(self, job_id):
        self.job_id = job_id

    def write(self, s):
        with _jobs_lock:
            _jobs[self.job_id]["log"] += s
        return len(s)


def start_job(kind, target):
    global _current_job_id
    with _jobs_lock:
        if _current_job_id is not None and _jobs[_current_job_id]["status"] == "running":
            raise HTTPException(409, "Another action is already running. Wait for it to finish first.")
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {
            "status": "running", "log": "", "result": None, "error": None,
            "kind": kind, "started_at": time.time(),
        }
        _current_job_id = job_id

    def runner():
        global _current_job_id
        buf = _LiveLog(job_id)
        try:
            with contextlib.redirect_stdout(buf):
                result = target()
            with _jobs_lock:
                _jobs[job_id]["result"] = result
                _jobs[job_id]["status"] = "done"
        except Exception as e:
            with _jobs_lock:
                _jobs[job_id]["log"] += f"\nERROR: {e}\n"
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(e)
        finally:
            with _jobs_lock:
                if _current_job_id == job_id:
                    _current_job_id = None

    threading.Thread(target=runner, daemon=True).start()
    return job_id


@app.get("/api/jobs/{job_id}")
def api_job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return {"status": job["status"], "log": job["log"], "result": job["result"], "error": job["error"], "kind": job["kind"]}


# ---------------------------------------------------------------------
# Health / screens / drive months
# ---------------------------------------------------------------------

@app.get("/api/health")
def api_health():
    return {"ok": True}


@app.get("/api/screens")
def api_screens():
    """Every screen in the AbleSign account - used by every screen dropdown
    in the app (playlist viewer, now-on-screen, delete playlist)."""
    return common.list_screens()


@app.get("/api/drive/months")
def api_drive_months():
    """Subfolders of the Drive 'Programming' parent folder, e.g.
    '8. August', '9. September' - used by the Upload Content and Create
    Playlist month dropdowns."""
    months = common.rclone_list_subfolders(common.PARENT_DRIVE_FOLDER_ID)
    return [{"name": name, "drive_id": fid} for name, fid in months]


# ---------------------------------------------------------------------
# Schedule (schedule.csv)
# ---------------------------------------------------------------------

@app.get("/api/schedule")
def api_get_schedule():
    rows = common.load_schedule_rows(SCHEDULE_CSV)
    return {"rows": [{"id": i, **r} for i, r in enumerate(rows)], "day_names": common.DAY_NAMES}


@app.post("/api/schedule")
def api_save_schedule(body: dict):
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "rows must be a non-empty list")

    day_by_lower = {d.lower(): d for d in common.DAY_NAMES}
    cleaned = []
    for i, r in enumerate(rows):
        cls = str(r.get("class", "")).strip()
        day_raw = str(r.get("day", "")).strip()
        start_raw = str(r.get("start", "")).strip()
        end_raw = str(r.get("end", "")).strip()

        if not cls:
            raise HTTPException(400, f"Row {i + 1}: class name is required")
        day = day_by_lower.get(day_raw.lower())
        if day is None:
            raise HTTPException(400, f"Row {i + 1} ({cls}): '{day_raw}' is not a valid day")
        try:
            start = common.normalize_time(start_raw)
            end = common.normalize_time(end_raw)
        except Exception:
            raise HTTPException(400, f"Row {i + 1} ({cls}): start/end must be HH:MM")
        if start >= end:
            raise HTTPException(400, f"Row {i + 1} ({cls}, {day}): start must be before end")

        cleaned.append({"class": cls, "day": day, "start": start, "end": end})

    common.save_schedule_rows(SCHEDULE_CSV, cleaned)
    return {"ok": True, "row_count": len(cleaned)}


# ---------------------------------------------------------------------
# Live AbleSign playlist viewing
# ---------------------------------------------------------------------

@app.get("/api/playlist")
def api_playlist(screen_ids: str):
    """screen_ids is a comma-separated list, e.g. '499083,499094,499095'.
    Returns each screen's full weekly playlist (unfiltered) for the
    Playlist Viewer page."""
    ids = [int(x) for x in screen_ids.split(",") if x.strip()]
    screens_by_id = {s["id"]: s["title"] for s in common.list_screens()}
    result = []
    for sid in ids:
        rows = common.get_playlist_rows(sid)
        result.append({"screen_id": sid, "screen_title": screens_by_id.get(sid, f"Screen {sid}"), "rows": rows})
    return {"screens": result, "day_names": common.DAY_NAMES}


@app.get("/api/playlist/{screen_id}/now")
def api_playlist_now(screen_id: int):
    """What's actually live on this screen right now (day/time AND
    periodic-date-range aware) - for the 'Now on screen' page."""
    current_day, current_time = common.current_day_and_time()
    day_full = common.DAY_NAMES[common.ALL_DAY_KEYS.index(current_day)]
    rows = common.get_playlist_rows(screen_id)
    live = [r for r in rows if common.is_row_live_now(r, current_day, current_time)]
    return {"current_day": day_full, "current_time": current_time, "rows": live}


@app.post("/api/playlist/{screen_id}/delete")
def api_playlist_delete(screen_id: int, body: dict):
    """Clears a screen's playlist. The frontend must have already gotten
    an explicit typed 'DELETE' confirmation before calling this - body.
    confirmed is a defense-in-depth check, not the only one."""
    if not body.get("confirmed"):
        raise HTTPException(400, "confirmed must be true")
    playlist = common.get_playlist(screen_id)
    before = len(playlist.get("items", []))
    common.clear_playlist(screen_id)
    return {"ok": True, "cleared_count": before}


# ---------------------------------------------------------------------
# Upload content (Drive -> AbleSign), background job
# ---------------------------------------------------------------------

@app.post("/api/upload")
def api_upload(body: dict):
    month = body.get("month")
    if not month:
        raise HTTPException(400, "month is required")
    dry_run = bool(body.get("dry_run", False))
    job_id = start_job("upload", lambda: upload_content.run(month, dry_run))
    return {"job_id": job_id}


# ---------------------------------------------------------------------
# Create playlist: fast synchronous preview (dry-run, all 3 screens),
# then a background job for the real push.
# ---------------------------------------------------------------------

@app.get("/api/playlist/create/preview")
def api_create_preview(folder: str):
    screens = common.load_screens()  # {"TV1": 499083, "TV3": 499094, "TV5": 499095}
    results = []
    total_would_add = 0
    total_already_present = 0

    for tag, screen_id in screens.items():
        screen = common.get_screen_by_id(screen_id)
        added, already_present, details = create_playlist.run(
            screen, tag, folder, SCHEDULE_CSV, common.DURATION, True
        )
        total_would_add += added
        total_already_present += already_present
        results.append({
            "tag": tag, "screen_id": screen_id, "screen_title": screen["title"],
            "would_add": added, "already_present": already_present, "items": details,
        })

    return {
        "screens": results,
        "total_would_add": total_would_add,
        "total_already_present": total_already_present,
    }


@app.post("/api/playlist/create/execute")
def api_create_execute(body: dict):
    folder = body.get("folder")
    if not folder:
        raise HTTPException(400, "folder is required")
    job_id = start_job(
        "create_playlist",
        lambda: create_playlist.run_all_screens(folder, SCHEDULE_CSV, common.DURATION, False),
    )
    return {"job_id": job_id}
