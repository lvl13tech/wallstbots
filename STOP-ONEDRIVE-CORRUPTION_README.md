# Stop OneDrive From Corrupting the Claude Projects

**Problem:** Your laptop force-enables OneDrive, and your code lives under
`C:\Users\temps\OneDrive\Desktop\Claude\…`. OneDrive syncs files **while they are
being written**, which leaves them **truncated** (cut off mid-file) or full of
**NUL bytes** — the recurring breakage we keep having to restore from git.

**Goal:** Tell OneDrive to leave the entire `Claude` folder alone. The files stay
exactly where they are on disk; OneDrive simply stops touching them. This protects
**this repo and every other Claude project** under `Desktop\Claude`.

---

## Do this once (5 minutes)

### Step 1 — Open OneDrive settings
1. Click the **OneDrive cloud icon** in the system tray (bottom-right, near the clock).
   If you don't see it, click the **^** "show hidden icons" arrow.
2. Click the **gear ⚙ icon** → **Settings**.

### Step 2 — Exclude the Claude folder from syncing
You'll use whichever of these your build of OneDrive shows (they do the same thing):

**Option A — "Choose folders" (most common):**
1. In Settings, go to the **Account** tab.
2. Click **Choose folders**.
3. You'll see a tree of your OneDrive folders. Expand **Desktop**.
4. **Uncheck** the **`Claude`** folder.
5. Click **OK**. OneDrive stops syncing everything under `Desktop\Claude`.

**Option B — "Exclude folders from sync" (newer OneDrive):**
1. Settings → **Sync and back up** → **Advanced settings**.
2. Under **Exclude folders from sync**, click **Add folder**.
3. Select `Desktop\Claude`. Confirm.

> If **Desktop** is being backed up via "Back up folders" (PC folder backup) and that
> won't let you uncheck a subfolder, see Step 4 (fallback).

### Step 3 — Verify it worked
After excluding, the `Claude` folder's icon should **lose the green-check / cloud
sync badge** (it'll show no OneDrive status icon). Then run:

> **`VERIFY-not-synced_2026-06-28.bat`** (in this folder)

It writes a test file, waits, and confirms the file is **not** altered — i.e. OneDrive
is no longer touching the folder. It changes nothing in the repo.

### Step 4 — Fallback if you CANNOT exclude a backed-up Desktop subfolder
Some managed laptops force "Desktop backup" and won't let you uncheck a subfolder.
Two clean fallbacks (pick one):
- **Add a `.nosync`-style block:** rename the folder to end in a OneDrive-ignored
  pattern is NOT reliable on managed tenants — prefer the next option.
- **Move the Claude folder OFF the Desktop** to a non-synced path, e.g.
  `C:\Claude\` (root of C:, outside OneDrive). Everything keeps working; you just
  open the project from the new path. If you want this route, tell Claude and it
  will give you a one-time move script + update any path references.

---

## Why this is the right fix (and what it does NOT change)
- The repo's **git** is already safe — `.git` was relocated to `C:\GitRepos\WallStBots.git`
  via a junction, so git internals don't corrupt. This step protects the **working
  files** (the .py/.html/.js you edit), which is the part still in OneDrive.
- Excluding from sync does **not** delete anything and does **not** affect GitHub —
  you still commit/push exactly as now. You only lose OneDrive's cloud copy of these
  files, which you don't want anyway (GitHub is the real backup).
- `.gitattributes` already normalizes line endings (`eol=lf`), which reduces churn —
  but it can't stop OneDrive writing a half-synced file. Only excluding the folder does.

---

## If corruption ever appears again after this
It shouldn't — but the guards stay in place as insurance:
- Every deploy `.bat` runs the **truncation guard** + a **NUL-byte check** before pushing.
- Recovery is always: restore the file from git, then re-apply (Claude has done this
  repeatedly and it's quick).
- Tell Claude "corruption is back" and it will check whether the OneDrive exclusion
  actually took effect (Step 3 verify) before doing anything else.
