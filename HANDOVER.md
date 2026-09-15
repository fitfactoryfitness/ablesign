# Handover — AbleSign Automation (TV Screens)

**In plain terms:** these are the scripts that put class slides on the gym's TVs
(DRILLROOM TV1/TV3/TV5) and control when they show. There's no app to open — someone types a
short command in Terminal.

**Owner until 2026-09-29:** Lucas Rietsch (lucas@fitfactoryfitness.com).

## Do you need to touch any code?

**Yes — this one requires someone willing to run commands, but no coding knowledge.**
[README.md](README.md) is already written assuming the reader has never used Terminal or git
before — it spells out every click and keystroke. Whoever takes this over should start there,
not with this document.

**If nobody taking over is willing to follow a step-by-step Terminal guide,** this needs to
go to someone technical, or the gym needs a different way to update TV content going forward.

## Setting up access (do this before 2026-09-29)

### 1. AbleSign account
The new operator needs their own login (or access to the shared one) at ablesign.tv, with
visibility into the DRILLROOM screens (TV1, TV3, TV5). Ask Lucas who currently has admin
rights on the AbleSign account and get the new person added there.

### 2. The API key these scripts use
**Decision: keeping the same API key rather than issuing a new one.** It's already in
[AI_HANDOFF.md](AI_HANDOFF.md) and in the real (not-committed-to-git) `.ablesign_api_key`
file. Copy that file to whichever computer runs these scripts next — Lucas can hand it over
directly or through a password manager.

### 3. Google Drive access (where the class slide images come from)
This uses a tool called `rclone` to read a specific Google Drive folder — set up per computer,
not something that transfers automatically. README.md Part 1 covers this step by step.

### 4. GitHub (where the code itself lives)
Nothing you need to do unless you're editing the scripts yourself. Lucas will move this
repository into a Fit Factory GitHub organization — see the master handover plan.

## Deeper technical notes

[AI_HANDOFF.md](AI_HANDOFF.md) has the full technical writeup (API endpoints, known gotchas,
screen IDs) for whoever ends up maintaining or extending this.
