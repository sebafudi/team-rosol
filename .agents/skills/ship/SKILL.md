---
name: ship
description: Ship finished work to main. Use when a task is done or the user says /ship — sync main, commit, open PR, merge.
---

# /ship

1. `git fetch origin && git merge origin/main` — resolve conflicts, keep it running.
2. Commit any finished, uncommitted units (atomic, per AGENTS.md).
3. `git push -u origin HEAD`
4. `gh pr create --fill --base main` (reuse the PR if it exists).
5. `gh pr merge --merge` — no squash/rebase; history is the audit trail.
6. Report the PR URL.
