---
type: eval
skill: spawn-agent
scenario: merge_agent
description: User asks to merge an agent's finished work into the current branch
---

## Input

User says:
> "The feat/oauth2 agent finished. Merge its work into my current branch."

## Expected behavior

1. Skill triggers
2. Uses `git merge feat/oauth2` from the current branch (not copy/checkout files)
3. If conflicts arise, reports them to the user instead of resolving silently
4. Confirms the merge was successful with a summary of what was integrated
5. Does NOT run `git log` from the worktree directory on the host (the `.git` file
   contains a container path and will fail) — verifies with `git log feat/oauth2`
   from the main repo if needed

## Must NOT do

- Must NEVER copy files from the worktree directory — always use `git merge`
- Must not delete the worktree or branch unless the user explicitly asks
- Must not force-push or rebase without user confirmation
