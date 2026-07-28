---
type: eval
skill: spawn-agent
scenario: multi_agent
description: User spawns multiple agents in parallel for different tasks
---

## Input

User says:
> "I want three agents in parallel: one to implement OAuth, one to write tests for
> the existing auth module, and one to do mutation testing on the payment service."

## Expected behavior

1. Skill triggers once and handles all three
2. Generates distinct branches if not specified:
   - `feat/oauth` (feature agent)
   - `test/auth` (test agent)
   - `mutation/payment` (mutation agent)
3. Builds **type-appropriate prompts** for each
4. Launches 3 `container run -d` commands sequentially
5. Lists all 3 containers at the end with:
   ```bash
   container list | grep "<project-name>"   # basename of git root, e.g. stackai
   ```
6. Tells user how to monitor each one

## Must NOT do

- Must not use the same branch/container name for different agents
- Must not use the same generic prompt for all three (prompts differ by type)
- Must not block waiting for any agent to finish
