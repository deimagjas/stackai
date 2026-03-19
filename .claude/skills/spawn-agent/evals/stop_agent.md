---
type: eval
skill: spawn-agent
scenario: stop_agent
description: User asks to stop a running agent
---

## Input

User says:
> "Stop the feat/jwt-auth agent and clean up its worktree."

## Expected behavior

1. Skill triggers
2. Sanitizes branch for container name: `feat-jwt-auth`
3. Runs: `container stop qubits-team-feat-jwt-auth`
4. If user asked to clean worktree, also runs:
   ```bash
   git -C <git-root> worktree remove --force <worktrees-dir>/feat/jwt-auth
   rm -rf <worktrees-dir>/feat/jwt-auth
   ```
5. Confirms the agent was stopped

## Must NOT do

- Must not delete the worktree unless user explicitly asked
- Must not fail silently if container doesn't exist (report it)
