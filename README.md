# AbleSign push, terminal-only, no GCP account

This version doesn't touch the Google Drive API at all, so there's no GCP
project, no OAuth consent screen, none of that. Instead it uses **rclone**,
a command-line tool that already has its own registered Google app, to pull
files down from Drive, then a plain Python script pushes them to AbleSign.

Everything runs from your terminal, on your own laptop (not in a sandbox),
so it has normal internet access to both Google and AbleSign.

## 1. Install rclone (one time)

macOS:
```
brew install rclone
```
(Linux: `sudo apt install rclone` or see https://rclone.org/downloads/)

## 2. Connect rclone to your Google account (one time)

```
rclone config
```

Walk through the prompts:
- `n` for new remote
- name: `gdrive`
- storage type: pick the number next to **Google Drive** in the list
- client_id: leave blank (press Enter)
- client_secret: leave blank (press Enter)
- scope: pick **2** (read-only access, `drive.readonly`), unless you plan
  to extend this script to upload back into Drive later
- root_folder_id: leave blank
- service_account_file: leave blank
- Edit advanced config: `n`
- Use auto config (opens a browser to log in): `y`
- Log in with the Google account that has access to the Fit Factory Drive,
  approve access
- Configure as a Shared Drive: `n` (unless your Fit Factory files live in
  an actual Shared Drive, not a shared folder, in which case `y`)
- Confirm the new remote: `y`, then `q` to quit config

Test it worked:
```
rclone lsf "gdrive:Testing/LOUNGE MAIN SCREEN"
```
You should see the slide's filename printed back.

## 3. Install the Python dependency

```
pip install -r requirements.txt
```

## 4. Set your AbleSign API key

```
export ABLESIGN_API_KEY="ak_1c9d0575130dabc8d361567017896164eae8c52c"
```

Don't put this in any file that ends up in Drive or shared storage. This
export only lives in your current terminal session (add it to your shell
profile, e.g. `~/.zshrc`, if you want it to persist across sessions,
but keep that file local to your own machine).

Consider rotating this key in AbleSign's Account > API Keys once you're
done testing, since it was shared in a chat transcript.

## 5. Run the test case

Preview only, touches nothing in AbleSign:
```
./push_slide.sh "Testing/LOUNGE MAIN SCREEN" --day fri --start 09:00 --end 12:00 --dry-run
```

If the folder name and file listed look right, run it for real:
```
./push_slide.sh "Testing/LOUNGE MAIN SCREEN" --day fri --start 09:00 --end 12:00
```

Then check the AbleSign CMS: the screen titled "LOUNGE MAIN SCREEN" should
have a new playlist item scheduled for Friday 9:00–12:00.

(First time only: `chmod +x push_slide.sh` if your terminal complains about
permissions.)

## How it fits together

`push_slide.sh` does two things: pulls the named Drive folder down to a
temp directory with `rclone copy`, then calls `ablesign_push.py` against
that local folder. `ablesign_push.py` itself never talks to Google, it
just reads whatever files are already on disk and pushes them to AbleSign
via the documented REST API (upload, then add to that screen's playlist
with the day/time window you passed in). The temp folder is deleted
automatically when the script finishes.

## Known constraint worth knowing

AbleSign screen titles must be unique and must match the Drive folder name
exactly (case-insensitive) for the matching to work. If two screens ever
share a title, or a folder gets renamed out of sync with AbleSign, the
script stops with an error rather than guessing.
