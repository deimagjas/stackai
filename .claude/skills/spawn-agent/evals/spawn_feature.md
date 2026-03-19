---
type: eval
skill: spawn-agent
scenario: spawn_feature
description: User asks to spawn an agent to implement a new feature
---

## Input

User says:
> "Spawn an agent to implement JWT authentication in the API. Use branch feat/jwt-auth."

## Expected behavior

1. Skill triggers automatically (no `/` needed)
2. Determines agent type = **feature**
3. Detects git root from current directory
4. Builds task prompt for feature type mentioning "JWT authentication in the API"
5. Sanitizes branch: `feat/jwt-auth` → container name `qubits-team-feat-jwt-auth`
6. Checks `CLAUDE_CONTAINER_OAUTH_TOKEN` is set (warns if not)
7. Runs `container run -d --rm ...` with:
   - `--worktree feat/jwt-auth`
   - `--task "...JWT authentication..."`
   - `-v <git-root>:/workspace`
   - `-v <parent>/.worktrees:/worktrees`
8. Confirms container started with `container list`
9. Reports container name and how to follow logs

## Must NOT do

- Must not use `make spawn` (skill runs container directly)
- Must not block waiting for the agent to finish
- Must not use a named Docker volume
