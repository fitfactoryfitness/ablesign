# AbleSign Control Panel

This is a simple app for managing what shows on the gym's TV screens
(DRILLROOM TV1/TV3/TV5) — the weekly class schedule, uploading new slides,
and pushing them to the screens — without needing to touch AbleSign
directly.

This guide assumes you've never used Terminal or git before. Every step is
spelled out.

---

## Part 1 — One-time setup

You only ever do this once, on your own laptop.

### Step 1: Install two free programs

1. **Node.js** — go to [nodejs.org](https://nodejs.org), download the
   installer for Mac, open it, click through like any normal app install.
2. **Python** — Macs already come with this, you don't need to install
   anything.

### Step 2: Get the project files onto your computer

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
   on your Desktop. That's the whole app.

### Step 3: Get the AbleSign key from Lucas

The app needs a small key file to talk to AbleSign. Ask Lucas to send you
the file named `.ablesign_api_key` (AirDrop, Slack, text — doesn't
matter). Drag that file directly into the `ablesign-automation` folder on
your Desktop.

You won't see it appear in the folder afterward — that's normal, files
starting with a dot are hidden by Finder. As long as you dragged it in,
it's there.

That's it for one-time setup.

---

## Part 2 — Using the app, every time

1. Open the `ablesign-automation` folder on your Desktop.
2. Double-click **`Start AbleSign App.command`**.
3. A black Terminal window opens and text starts scrolling — this is
   normal. The first time can take a minute or two (installing things);
   after that it's much faster. Wait until you see a line that says
   `ready`.
4. Open your web browser (Safari, Chrome, whatever you normally use) and
   go to:
   ```
   http://127.0.0.1:5173
   ```
5. Use the app normally (see the tour below).
6. When you're done, go back to that black Terminal window and either
   close it, or click inside it and press `Ctrl + C`.

Every time you double-click the launcher, it automatically checks GitHub
for the newest version of the app first — you never need to remember to
update anything yourself.

---

## Part 3 — A quick tour of each page

- **Weekly Schedule** — the master weekly schedule. Drag a class card to
  a different day, click a card to edit its time, or duplicate/delete it.
  Changes aren't saved until you click **Update the schedule** and
  confirm.
- **Playlist Viewer** — a read-only view of exactly what's currently
  scheduled on each screen, straight from AbleSign. Safe to open anytime.
- **Now On Screen** — pick a screen, see exactly what should be playing
  on it at this exact moment.
- **Upload Content** — pulls that month's class slides from Google Drive
  and uploads them into AbleSign. Doesn't put anything on a screen yet.
- **Create Playlist** — takes whatever's been uploaded plus the current
  Weekly Schedule and pushes it live to TV1/TV3/TV5. Always shows you a
  preview of exactly what will change before you confirm.
- **Delete Playlist** — wipes everything off one screen. Permanent, so it
  makes you type the word `DELETE` to confirm.

Every button that changes something real always asks you to confirm
first — nothing happens from a single accidental click.

---

## If something goes wrong

- **The Terminal window shows red/error text** — take a screenshot and
  send it to Lucas.
- **"Address already in use"** — you probably already have the app
  running in another window somewhere. Close other Terminal windows and
  try again.
- **The browser page won't load** — wait a little longer, the first
  start-up can be slow, then refresh the page.
- **Upload Content doesn't work** — this one feature needs a bit of extra
  one-time setup with Lucas (Google Drive access). Everything else on
  this page works without it.

If none of that helps, screenshot whatever the Terminal window says and
send it to Lucas — that's always the fastest way for him to figure out
what happened.
