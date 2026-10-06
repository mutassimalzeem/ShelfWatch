# ShelfWatch Git Workflow Guide

How the scraper-correctness fix was landed "like a developer", plus a
practical cheat-sheet you can reuse. Every command below was actually used
in this repo (Windows PowerShell; paths quoted because of spaces).

## 0. Prerequisites

```powershell
git remote -v                 # confirm origin points at your GitHub repo
git switch main               # start from main            (old: git checkout main)
git pull --ff-only origin main                            # fast-forward to latest
git status                    # must be clean before branching
```

## 1. Annotated log of this session

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

3. **Untrack files that were committed by mistake but must stay on disk**
   (our `_*.py` / `_*.txt` / `_*.bat` debug scratch files). First add ignore
   rules to `.gitignore`, then:

   ```powershell
   git rm --cached scraper/_full_run.txt scraper/_probe_pages.py   # …all 13 files
   ```

   `--cached` removes them from the *index* only; the files remain in your
   working folder, and `.gitignore` keeps them untracked forever after.

4. **Stage per logical area and commit small, focused commits**
   (message style: `type: imperative summary`, ≤ ~72 chars, body explains why):

   ```powershell
   git add .gitignore
   git commit -m "chore: ignore session scratch files and untrack committed probes"

   git add scraper/config.py scraper/main.py scraper/scraper_shwapno.py `
             scraper/scraper_othoba.py scraper/README.md
   git commit -m "fix: scraper correctness (shwapno prices, othoba pager, daraz gate)"

   git add src/storage/db.py src/features/pack_parser.py src/__init__.py `
             src/eda/__init__.py src/features/__init__.py src/storage/__init__.py `
             run_crawler_scheduler.py
   git commit -m "fix: idempotent UTC-preserving ingestion, hardened scheduler"

   git add tests/test_smoke.py docs/GIT_WORKFLOW.md
   git commit -m "test: stdlib smoke tests; docs: git workflow guide"
   ```

5. **Push the branch and set its upstream** (`-u` remembers origin/branch so
   later plain `git push` / `git pull` work):

   ```powershell
   git push -u origin fix/scraper-correctness
   ```

6. **Merge into main with a merge commit** (keeps the feature history visible):

   ```powershell
   git switch main
   git merge --no-ff fix/scraper-correctness
   git push origin main
   ```

7. **Clean up the branch** once merged:

   ```powershell
   git branch -d fix/scraper-correctness
   git push origin --delete fix/scraper-correctness
   ```

> Note: the GitHub CLI (`gh`) is not installed on this machine, so no pull
> request was opened; push + merge was done with plain git. If you want PRs,
> install GitHub CLI or use the web UI between steps 5 and 6.

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

## 4. Follow along with this session's push

```powershell
git log --oneline --graph --decorate -12   # see branch + merge topology
git show --stat HEAD~3                     # inspect any commit's file list
```
