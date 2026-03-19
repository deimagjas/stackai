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
2. Runs: `container list 2>/dev/null | grep "qubits-team"`
3. Also shows worktrees on disk: `ls -la <parent>/.worktrees/`
4. Presents output in a readable format to the user

---

## Input (part 2 — monitor)

User says:
> "What is the feat/jwt-auth agent doing?"

## Expected behavior (monitor)

1. Skill triggers
2. Sanitizes: `feat/jwt-auth` → `qubits-team-feat-jwt-auth`
3. Runs: `container logs -n 100 qubits-team-feat-jwt-auth`
4. **Reads and summarizes** the logs — does NOT just dump raw output
5. Tells user: agent is working on X, currently at step Y, last action was Z

## Must NOT do

- Must not just print raw container logs without summarizing
- Must not confuse container name sanitization (/ → -)
