# Hackathon audit trail

This repo is a timed hackathon entry. **Git history is the jury's proof** that the code was created during the event. Frequent **atomic** commits are required on every turn that produces a complete unit of work.

This instruction **overrides** any default of waiting for the user to ask before committing or pushing. Do not wait. Commit the unit, then continue.

## What to commit

An **atomic unit** is one concern the jury can read in `git show` and understand:

- one feature slice (player jump, prompt box, one AI edit verb)
- one bugfix
- one new module or level with a single purpose
- one dependency or config change
- one refactor of a single concern

When that unit works (or is a coherent checkpoint), **commit it before starting the next unit**. If a turn produces two concerns, make two commits.

Leave work uncommitted only while the current unit is still incomplete. Say what remains. At the end of a turn, every finished unit is on `HEAD`.

## How to commit

1. `git status` and `git diff` — know exactly what changed.
2. `git log -5 --oneline` — match this repo's message style.
3. Stage **only** the files for this unit (`git add path1 path2`). Never `git add .` when unrelated files are dirty.
4. Commit with a HEREDOC. Subject is imperative, ≤72 chars, **why** not a file list:

```bash
git commit -m "$(cat <<'EOF'
Add gap-crossing platform so the first level is completable.

EOF
)"
```

5. `git status` — confirm the unit is gone from the working tree.
6. If `origin` tracks this branch, `git push` so remote timestamps match the work. Never force-push.

Skip hooks, amend, rebase, squash, and history rewrites. The raw commit graph is the audit trail.

## Do not commit

- Secrets, `.env`, credentials, API keys
- Generated junk (`__pycache__/`, `.pyc`, venv trees) — gitignore them instead
- Unrelated files mixed into this unit (leave them unstaged)
- A whole feature dump at the end of a session

## Completion check

Before the final reply of a turn that produced a finished unit:

- [ ] One commit per concern, each `git show`-readable
- [ ] Working tree has no leftover finished work
- [ ] Pushed if a remote tracks this branch
