---
type: eval
skill: spawn-agent
scenario: list_and_monitor
description: User asks to list agents and check what one is doing
---

## Input (part 1 — list)

User says:
> "Show me the active agents."

## Expected behavior (list)

1. Skill triggers
2. Runs: `container list 2>/dev/null | grep "<project-name>"` (basename of git root, e.g. `stackai`)
3. Also shows worktrees on disk (with status from `status.json` if available)
4. Presents output in a readable format to the user

---

## Input (part 2 — monitor)

User says:
> "What is the feat/jwt-auth agent doing?"

## Expected behavior (monitor)

1. Skill triggers
2. Reads `status.json` from `$AGENTS_HOME/feat/jwt-auth/.agent/status.json` for quick status
3. If more detail needed, reads container logs or persisted `.agent/agent.log`
4. Sanitizes container name correctly: `feat/jwt-auth` → `<project-name>-feat-jwt-auth`
5. **Reads and summarizes** the output — does NOT just dump raw logs
6. Tells user: agent is working on X, currently at step Y, last action was Z

---

## Input (part 3 — status post-exit)

User says:
> "What happened with the feat/jwt-auth agent?"

## Expected behavior (status post-exit)

1. Skill triggers
2. Reads `status.json` from `$AGENTS_HOME/feat/jwt-auth/.agent/status.json`
3. Reports phase (completed/errored), exit code, commit count, duration
4. Does NOT attempt `container logs` on a stopped container
5. If user wants full logs, reads from `.agent/agent.log` (persisted)

## Must NOT do

- Must not just print raw container logs without summarizing
- Must not confuse container name sanitization (/ → -)
- Must not show errors when container is gone (use persisted files instead)
