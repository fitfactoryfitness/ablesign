# AbleSign Scripts

Commands for managing what shows on the gym's TV screens (DRILLROOM
TV1/TV3/TV5) — uploading class slides, scheduling them, checking what's
live. There's no app to open — you type a command in Terminal for
whatever you want to do.

This guide assumes you've never used Terminal or git before. Every step
is spelled out.

---

## Part 1 — One-time setup

You only ever do this once, on your own laptop.

### Step 1: Get the project files onto your computer

1. Press `Cmd + Space`, type `Terminal`, press Enter. A black window opens
   — that's Terminal.
2. Copy this whole block, paste it into that window, press Enter:
   ```
   cd ~/Desktop && git clone https://github.com/lucasrfitfactory-create/ablesign.git ablesign-automation
   ```
3. The first time you ever use `git`, macOS may pop up a box asking to
   install "Command Line Developer Tools." Click **Install**, wait for it
   to finish, then run the same command above again.
4. When it's done, you'll have a new folder called `ablesign-automation`
   on your Desktop. That's everything.

### Step 2: Get the AbleSign key from Lucas

The scripts need a small key file to talk to AbleSign. Ask Lucas to send
you the file named `.ablesign_api_key` (AirDrop, Slack, text — doesn't
matter). Drag that file directly into the `ablesign-automation` folder.

You won't see it appear in the folder afterward — that's normal, files
starting with a dot are hidden by Finder. As long as you dragged it in,
it's there.

### Step 3 (only if you'll be uploading new content from Drive): rclone

If you'll be running "Upload Content" or "Update Program" yourself, ask
Lucas to walk you through setting up `rclone` (a one-time step that
connects to Google Drive). Everything else in this guide works fine
without it.

That's it for one-time setup.

---

## Part 2 — Every time you want to do something

1. Open the `ablesign-automation` folder on your Desktop.
2. Double-click **`Check for Updates.command`**. A black Terminal window
   opens, pulls the latest version, and checks everything's installed.
   Wait for it to say `All set`, then press Enter to close it.
3. Press `Cmd + Space`, type `Terminal`, press Enter.
4. Paste this once per Terminal window (it puts you in the right folder):
   ```
   cd ~/Desktop/ablesign-automation
   ```
5. Type/paste whichever command below matches what you want to do, and
   press Enter.

---

## Part 3 — The commands

For every action, there's usually a "preview" version (`--dry-run`) that
shows you exactly what would happen without changing anything — always
run that first to double check, then run the real version.

### Screens reference

| Name | Screen ID |
|---|---|
| DRILLROOM TV1 | `499083` |
| DRILLROOM TV3 | `499094` |
| DRILLROOM TV5 | `499095` |
| Headquarter (test screen) | `498279` |

### See what's on a screen right now
```
python3 list_playlist.py --screen-id 499083
```
Add `--full` to see the whole week instead of just this moment.

### Upload this month's slides from Drive into AbleSign
```
python3 upload_content.py --month "8. August" --dry-run
python3 upload_content.py --month "8. August"
```
This only uploads the files — it doesn't put anything on a screen yet.

### Push the schedule to all 3 screens (TV1/TV3/TV5)
```
python3 create_playlist.py --dry-run
python3 create_playlist.py
```
No flags needed — it always targets all 3 real screens using whatever's
in `schedule.csv` and whatever's already been uploaded. Rate-limited by
AbleSign, so a full push can take a couple hours; safe to stop (`Ctrl+C`)
and rerun the exact same command any time, it picks up where it left off.

### Clear everything off one screen
```
python3 delete_playlist.py --screen-id 499083 --dry-run
python3 delete_playlist.py --screen-id 499083 --yes
```
Permanent — there's no undo. `--yes` is required for the real run on
purpose, so you can't do this by accident.

### Refresh just ONE class's slides everywhere (without touching anything else)
```
python3 update_program.py --month "8. August" --program "ABS ASSAULT" --dry-run
python3 update_program.py --month "8. August" --program "ABS ASSAULT" --yes
```
Pulls new files for that one class from Drive, uploads them, and swaps
just that class's slides on all 3 screens — leaves every other class
completely alone. Old slides aren't deleted, just no longer shown.

### Test on the Headquarter screen first
```
python3 test.py --folder "Claude/8. August" --dry-run
python3 test.py --folder "Claude/8. August"
```
Same as "push the schedule," but only onto the Headquarter test screen —
useful for checking something looks right before pushing to the real TVs.

---

## Editing the weekly schedule

`schedule.csv` (inside the `ablesign-automation` folder) is the source of
truth for when each class shows. It's a plain spreadsheet file — open it
with Excel, Numbers, or Google Sheets, edit it, save it as a `.csv` file
with the same name. Columns: `Class`, `Day`, `Start`, `End` (24-hour time,
like `17:16`). Changes only take effect once you run `create_playlist.py`
again afterward.

---

## If something goes wrong

- **Red/error text in Terminal** — screenshot it and send it to Lucas.
- **A command says something like "not found" or "No module named..."**
  — run `Check for Updates.command` again, then retry.
- **Not sure what a flag like `--dry-run` does** — it's always safe: it
  only shows a preview, nothing in AbleSign changes.

If none of that helps, screenshot whatever Terminal says and send it to
Lucas — that's the fastest way for him to figure out what happened.
