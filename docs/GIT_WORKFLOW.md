# ShelfWatch Git Workflow Guide

Use small branches and pull requests so changes can be reviewed and tracked.
Commands below are written for Windows PowerShell.

## 0. Prerequisites

```powershell
git remote -v                 # confirm origin points at your GitHub repo
git fetch origin
git switch main
git pull --ff-only origin main
git status                    # review and preserve local changes
```

## 1. Make and submit a change

1. **Create + switch to a feature branch** (never commit fixes straight to main):

   ```powershell
   git switch -c fix/scraper-correctness      # -c = create + switch
   ```

   Naming convention: `fix/…`, `feat/…`, `chore/…`, `docs/…` + short slug.

2. **Work, then inspect constantly**:

   ```powershell
   git status --porcelain      # M = modified, ?? = untracked, D = deleted
   git diff                    # unstaged changes
   git diff --staged           # what is already queued for the next commit
   ```

3. **Stage per logical area and commit small, focused commits**
   (message style: `type: short summary`):

   ```powershell
   git add README.md docs\CASE_STUDY.md
   git commit -m "docs: update project and deployment notes"
   ```

4. **Push the branch and set its upstream** (`-u` remembers origin/branch so
   later plain `git push` / `git pull` work):

   ```powershell
   git push -u origin fix/scraper-correctness
   ```

5. **Open a pull request to `main`** in GitHub, review the changed files, and
   confirm the focused tests pass before merging.

6. **Clean up the branch** once merged:

   ```powershell
   git branch -d fix/scraper-correctness
   git push origin --delete fix/scraper-correctness
   ```

## 2. Daily cheat-sheet

### Inspect
| Command | Purpose |
|---|---|
| `git status --porcelain` | machine-readable working-tree state |
| `git log --oneline --graph --decorate -10` | recent history as a graph |
| `git show <commit>` | full diff of one commit |

### Branches & context switching
```powershell
git switch -c feat/x            # new branch (old: git checkout -b feat/x)
git switch main                 # change branch (old: git checkout main)
git branch -vv                  # list branches with upstreams
git switch -c hotfix/y origin/main   # branch from a remote state
```

### Stash — shelve unfinished work to switch context
```powershell
git stash push -m "wip: othoba pager"   # park current changes
git switch main                          # do something else (e.g. hotfix)
git switch fix/scraper-correctness
git stash pop                            # re-apply and drop the stash
git stash list                           # see all stashes
git stash apply stash@{0}                # apply without dropping
git stash drop stash@{0}                 # delete a stash
```

### Commit hygiene

Review a command before using it if it can discard uncommitted work.
`git restore <file>` discards changes to that file; `git reset` can move the
current branch pointer. Prefer `git status` and a backup branch when unsure.

```powershell
git add -p                      # stage hunk-by-hunk (review as you go)
git commit --amend              # fix message/content of LAST commit (pre-push)
git reset HEAD~1                # un-commit last commit, keep the changes
git restore <file>              # throw away working-tree edits to a file
git restore --staged <file>     # unstage a file
```

### Merges & conflicts
```powershell
git merge feat/x                # run while ON the target branch
# on conflict: edit files, then
git add <conflicted files>
git merge --continue            # or: git merge --abort to bail out
git merge --squash feat/x       # alternative: collapse feature into one commit
```

### Undo safely
```powershell
git revert <commit>             # new commit that undoes one (safe post-push)
git restore <deleted file>      # bring back a file you just deleted
git checkout <commit> -- <path> # resurrect a file from any old commit
```

### Remote
```powershell
git fetch origin                # download refs without merging
git pull --rebase origin main   # update local main linearly
git push -u origin <branch>     # first push of a branch
git push origin --delete <branch>
```

## 3. ShelfWatch repo conventions

- **Never commit**: `scraper/output/**`, `shelfwatch.db`, `_*.py`, `_*.txt`,
  `_*.bat`, `scheduler.lock` — all covered by `.gitignore`.
- Data (CSV snapshots, DB) stays local; only code, tests and docs travel
  through branch → merge → push.
- Before merging any branch: `python -m unittest discover -s tests -v`
  must pass from the repo root.

## 4. Release and deployment

```powershell
git log --oneline --graph --decorate -12   # inspect recent history
```

After a pull request is merged to `main`, Vercel automatically builds and
deploys the project. Check Vercel's deployment status and verify the
dashboard/API. GitHub Actions collects and ingests data separately, so check
its workflow run too.

This repository may be open in a Google Drive-synced folder. File locks have
prevented some Git and package operations; check `git status` and preserve
unrelated local changes rather than forcing cleanup.
