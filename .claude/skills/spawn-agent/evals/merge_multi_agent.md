---
type: eval
skill: spawn-agent
scenario: merge_multi_agent
description: User asks to merge multiple agent branches into a combined branch
---

## Input

User says:
> "Both agents are done — feat/oauth2 and test/auth-tests. Create a branch
> called integration/auth and merge both into it."

## Expected behavior

1. Skill triggers
2. Creates a new branch: `git checkout -b integration/auth`
3. Merges each agent branch sequentially:
   ```bash
   git merge feat/oauth2
   git merge test/auth-tests
   ```
4. Reports success after each merge; if a conflict occurs, stops and reports
   it to the user before attempting the next merge
5. Shows a final summary of the combined branch (commits from both agents)

## Must NOT do

- Must NEVER copy files from worktree directories — always use `git merge`
- Must not merge all branches in a single command (sequential merges allow
  conflict handling between each)
- Must not delete the original agent branches unless user explicitly asks
