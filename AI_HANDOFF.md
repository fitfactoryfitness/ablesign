# AbleSign automation for Fit Factory — handoff summary

## Goal
Automate pushing class slides from Google Drive to AbleSign digital signage,
including setting each screen's weekly display schedule, replacing the
manual "upload slide, add to playlist, set display times" workflow.

## Key facts learned

**AbleSign has a real REST API**, no need for browser automation.
Docs: https://apidocs.ablesign.tv/  Base URL: `https://api.ablesign.tv/api/v1`
Auth: `Authorization: Bearer <API_KEY>` header.

API key currently in use (hardcoded in the scripts, by explicit choice, for
convenience): `ak_1c9d0575130dabc8d361567017896164eae8c52c`
This key has been shared in a chat transcript — rotate it in AbleSign
(Account > API Keys) once things stabilize, and keep it out of anywhere
that gets shared/synced.

**Upload flow**: `POST /media_files/init_upload` (filename, mimeType, size)
returns a signed S3 URL + uploadId → `PUT` the file bytes to that URL →
`POST /media_files/finish_upload` (uploadId) → returns the media file id.

**Playlist scheduling**: `POST /screens/{id}/playlist_items`. Each item has
`monStart`/`monEnd` ... `sunStart`/`sunEnd` (HH:mm strings) plus
`scheduleEnabled: true`. **Important gotcha**: any day left unset defaults
to 00:00–23:59 (shown all day), NOT 00:00–00:00 (never shown). Every script
here explicitly zeroes out every day except the target one on every item it
creates.

**AbleSign has real nested folders** for organizing media (`POST /folders`
with `title` + `parentFolderId`, and `init_upload` accepts an optional
`folderId`), so AbleSign's content can mirror the Drive folder structure
exactly.

**Known AbleSign screens** (DRILLROOM room):
- TV1 = screen id 499083
- TV3 = screen id 499094
- TV5 = screen id 499095
- (also seen but unused so far: "PSC 1" = 499098, "LOUNGE MAIN SCREEN" used only for the initial test)

Assumption, unconfirmed: every class uses this same DRILLROOM TV1/TV3/TV5
trio. If some classes ever target a different room, this needs revisiting.

**AbleSign folder tree already created** for August:
`Claude` (id 87131) > `8. August` (id 87132) > 18 class subfolders (ids
87133–87150), one per class name, created via `ablesign_setup.py`.

## Network constraint (why things are built the way they are)

The Cowork sandbox this conversation runs in cannot reach `api.ablesign.tv`
(outbound proxy blocked by allowlist) and has no practical way to do Google
OAuth either. So **all scripts are meant to run on Lucas's own laptop**,
which has normal internet access. Nothing here executes from inside a
Cowork/Claude chat session directly.

## Google Drive access: rclone, not the Google API

No GCP account is available, so the Google Drive API (which needs an OAuth
client from a GCP project) was avoided entirely. Instead: **rclone**, which
ships with its own pre-registered Google client, no GCP project needed.

Setup done once: `brew install rclone`, then `rclone config`, remote named
exactly `gdrive`, Google Drive storage type, read-only scope, browser
auto-auth as `lucas.r.fitfactory@gmail.com`.

**Important gotcha**: this Drive content lives under "Shared with me", not
Lucas's own "My Drive" (owned by a mix of accounts: lucas.r.fitfactory,
sstalteri19, rhuynh88, etc.). Plain name-based path lookups
(`gdrive:Testing/LOUNGE MAIN SCREEN`) fail with "directory not found".
Fix: **always address folders by their Drive folder ID**, using rclone's
connection-string syntax: `gdrive,root_folder_id=<ID>:`. This works
regardless of ownership and doesn't break if something gets renamed.

## Drive folder structure (source of truth for slides)

Root "Programming" folder: `1sm9n_jKbWJEkBd-ziiyBTrvjbwJyK-ye`
(https://drive.google.com/drive/folders/1sm9n_jKbWJEkBd-ziiyBTrvjbwJyK-ye)

Convention: **Month folder** (e.g. "8. August", id
`1l_C_uoSo2Rkln2QsMlj85wKnEh92Jg__`) containing **one folder per class**.
The class folder's name must match the schedule's Class column **exactly**
(case-insensitive), no numbering prefixes. Each class folder holds exactly
3 files, filenames just need to contain "TV1", "TV3", or "TV5" somewhere
(rest of the filename is free text).

18 class folders already created under "8. August" in Drive, matching the
18 class names in the schedule (see classes.txt). They're currently empty,
waiting for Lucas to drop slides in.

Test folder used to validate the whole pipeline end to end:
"Testing" > "LOUNGE MAIN SCREEN" (id `1-QJlITGPo-gvWflO8EKU5wamzSS0gMYg`),
pushed successfully to AbleSign screen "LOUNGE MAIN SCREEN", Friday
09:00–12:00. This confirmed the full chain works: Drive → rclone → local
file → AbleSign upload → scheduled playlist item.

## Schedule source of truth

Google Sheet "1. SCHEDULE 2026"
(id `11uDTIlwLDBhhIHfEMTy-i4gZdi4t_bv8BnNHcoxosmA`), tab named
**"AI SCHEDULE"**, moved to be the **first (leftmost) tab** in the file.
Flat format, one row per weekly occurrence:

```
Class,Day,Start,End
HYROX CONDITIONING,Tuesday,05:00,07:15
HYROX CONDITIONING,Tuesday,08:31,13:00
...
```

Classes that air twice in one day (e.g. HYROX CONDITIONING on Tuesday) just
get two rows — this is exactly what drives the "add it twice" behavior
automatically, no special folder naming needed for that case.

**Important gotcha**: Google's CSV export of a multi-tab spreadsheet only
grabs the first tab, hence moving AI SCHEDULE to be first. Even more
reliable: before each batch run, manually export it yourself (Google
Sheets > File > Download > Comma-separated values, current sheet) and save
as `schedule.csv` next to the batch script. This sidesteps any tab-order
ambiguity entirely and is what `ablesign_batch.py` expects.

## Scripts built (all currently sitting in the Cowork session's output
folder — grab the actual files, this summary alone isn't enough)

- **`ablesign_push.py`** — pushes ONE Drive folder (by ID) to ONE named
  AbleSign screen, with one day/time window. Used for the initial trust
  test. Superseded by `ablesign_batch.py` for real monthly use, but useful
  for one-off pushes.
- **`ablesign_setup.py`** — one-time helper. `--list-screens` prints all
  AbleSign screens (id + title). `--create-tree "Claude/8. August"
  --classes-file classes.txt` creates a nested AbleSign folder tree
  mirroring Drive; safe to re-run, reuses existing folders instead of
  duplicating.
- **`classes.txt`** — flat list of the 18 class names, one per line, used
  by `ablesign_setup.py --create-tree`.
- **`screens.json`** — TV1/TV3/TV5 → AbleSign screen id mapping.
- **`ablesign_batch.py`** — the main script. Reads `schedule.csv`, lists
  the class subfolders under a given Drive month folder (via
  `rclone lsjson`), matches each folder name to schedule rows (skips with
  a warning if no match, e.g. naming mismatch), uploads each TV-tagged file
  once per screen into the matching AbleSign folder, and creates one
  playlist item per schedule row per screen (handles multi-occurrence
  classes automatically). Always explicitly zeroes every non-target
  weekday. Supports `--dry-run` to preview without touching AbleSign.
- **`requirements.txt`**, **`README.md`** — setup docs (rclone install/
  config steps, `pip install requests`, notes on the hardcoded key).

## Current status

- AbleSign folder tree for August: done (`Claude/8. August` + 18 class
  folders).
- Drive folder tree for August: done (`8. August` + 18 class folders,
  currently empty).
- Schedule: in the "AI SCHEDULE" tab, confirmed accurate by Lucas.
- Slides: not yet added to the Drive class folders.
- `ablesign_batch.py`: written, dry-run tested successfully against the
  schedule matching logic (confirmed classes with multiple weekly
  occurrences produce the correct number of schedule slots), but NOT yet
  tested end-to-end with real files (folders are still empty).

## Next steps

1. Lucas drops 3 TV-tagged slides into each Drive class folder under
   "8. August".
2. Export the AI SCHEDULE tab to `schedule.csv` (File > Download > CSV,
   current sheet).
3. Run the dry run first:
   ```
   python3 ablesign_batch.py --drive-folder-id 1l_C_uoSo2Rkln2QsMlj85wKnEh92Jg__ \
     --ablesign-root "Claude/8. August" --schedule-csv schedule.csv --dry-run
   ```
4. Review the output, then re-run the same command without `--dry-run` to
   actually push everything.
5. For future months: create a new Drive month folder + matching class
   subfolders, re-run `ablesign_setup.py --create-tree "Claude/9. September"
   --classes-file classes.txt` (update classes.txt if the class roster
   changes), update the AI SCHEDULE tab, export a fresh schedule.csv, run
   `ablesign_batch.py` again with the new `--drive-folder-id` and
   `--ablesign-root`.

## Things a new session should NOT re-litigate

- Don't try to use the Google Drive API / OAuth / a GCP project — rclone
  already solves this without one.
- Don't rely on Drive path-by-name lookups — this Drive tree is
  shared-with-me, not owned; always use folder IDs.
- Don't leave AbleSign schedule days unset expecting them to default to
  "off" — they default to all-day; always zero explicitly.
- Don't assume Cowork's own sandbox can reach AbleSign or do a live OAuth
  browser flow — it can't; everything runs on Lucas's laptop.
