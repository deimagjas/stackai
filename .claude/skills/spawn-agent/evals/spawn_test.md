---
type: eval
skill: spawn-agent
scenario: spawn_test
description: User asks to spawn a test agent
---

## Input

User says:
> "Create a virtual agent to write unit tests for the auth module."

## Expected behavior

1. Skill triggers automatically
2. Determines agent type = **test**
3. Suggests or auto-generates branch name: `test/auth` (if user didn't specify)
4. Builds task prompt with QA/testing focus: coverage, edge cases, run & verify
5. Launches detached container with correct volumes
6. Confirms launch and shows how to monitor

## Must NOT do

- Must not confuse test agent with mutation agent
- Must not pick a feature-type prompt
