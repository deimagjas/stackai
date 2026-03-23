---
name: spawn-agent
description: >
  Launch, monitor, list, and stop virtual Claude agent containers that work in
  isolated git worktrees using Apple Container CLI. Use this skill when the user
  asks to: spawn/create/launch an agent or virtual agent, delegate a coding task
  to an agent, implement a feature in isolation, run unit tests or mutation tests
  via an agent, list/show active agents, check what an agent is doing, read agent
  output/logs, or stop/kill an agent.
allowed-tools: Bash, Read, Glob, Grep
---

# Virtual Agent Coordinator

You manage virtual Claude agents running as Apple containers. Each agent:
- Runs headlessly (`claude -p`) inside a container
- Works in an **isolated git worktree** (branch auto-created inside the container)
- Outputs to container logs (readable with `container logs <name>`)
- Exits when the task completes (container removed automatically with `--rm`)

## Required environment variables

Two host env vars must be set before spawning. Check them explicitly and tell the
user if either is missing — do not proceed without them.

| Variable | Purpose | Check |
|---|---|---|
| `CLAUDE_CONTAINER_OAUTH_TOKEN` | OAuth token for Claude inside container | `test -n "$CLAUDE_CONTAINER_OAUTH_TOKEN"` |
| `AGENTS_HOME` | Directory where worktrees are stored | `test -n "$AGENTS_HOME"` |

**If missing, show the user what to export:**
```bash
# AGENTS_HOME: parent directory where all agent worktrees will live
# Recommended: set once in ~/.zshrc or ~/.bashrc
export AGENTS_HOME=~/agents         # or any persistent path you prefer
export CLAUDE_CONTAINER_OAUTH_TOKEN=<your-oauth-token>
```

`AGENTS_HOME` replaces any hardcoded path. Each worktree lands at `$AGENTS_HOME/<branch>`.

## Path conventions

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
PROJECT_NAME=$(basename "$GIT_ROOT")          # e.g. stackai
WORKTREES_DIR="${AGENTS_HOME}"                # from env var, e.g. ~/agents
NETWORK=claude-agent-net
IMAGE=claude-agent:wolfi
```

Container names follow the pattern: `<project>-<sanitized-branch>`
Branch sanitization — each `/`, `_`, or space becomes a single `-`, lowercased:
```bash
CONTAINER_BRANCH=$(echo "${BRANCH}" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')
CONTAINER_NAME="${PROJECT_NAME}-${CONTAINER_BRANCH}"
# Example: stackai + feat/oauth2 → stackai-feat-oauth2
```

## Setup (one-time per project)

```bash
cd <git-root>/config && make build          # build claude-agent:wolfi image
export AGENTS_HOME=~/agents                 # set once in shell profile
export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>
```

## Prompts by agent type

Build the task prompt based on what the user wants:

**feature** — implement a new capability:
```
You are a senior software engineer. Implement the following in this codebase:
<user description>
Requirements:
- Write clean, tested, production-ready code
- Follow existing conventions (read the codebase first)
- Create a git commit when done with a descriptive message
```

**test** — write or improve unit tests:
```
You are a senior QA engineer. Your task:
<user description>
Requirements:
- Identify untested or poorly tested code
- Write comprehensive unit tests
- Aim for high coverage of edge cases
- Run the tests and verify they pass
- Commit the tests when done
```

**mutation** — mutation testing:
```
You are a mutation testing expert. Your task:
<user description>
Requirements:
- Analyze existing tests for weak assertions
- Introduce mutations and verify tests catch them
- Strengthen tests that miss mutations
- Report a summary of findings
- Commit improvements when done
```

**explore/other** — general task:
```
You are a senior software engineer. Your task:
<user description>
Work autonomously, read the codebase as needed, and commit any changes.
```

## Spawning an agent

**Step 1: Check env vars**
```bash
test -n "$CLAUDE_CONTAINER_OAUTH_TOKEN" || echo "ERROR: export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>"
test -n "$AGENTS_HOME"                  || echo "ERROR: export AGENTS_HOME=<path>"
```

**Step 2: Launch (detached)**
```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
PROJECT_NAME=$(basename "$GIT_ROOT")
CONTAINER_BRANCH=$(echo "${BRANCH}" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')
CONTAINER_NAME="${PROJECT_NAME}-${CONTAINER_BRANCH}"

# Ensure network exists (macOS 26+)
container network list --format json 2>/dev/null | grep -q '"claude-agent-net"' \
  || container network create --subnet 192.168.100.0/24 claude-agent-net

# Create worktrees dir
mkdir -p "${AGENTS_HOME}"

# Launch agent
container run -d --rm \
  --name "${CONTAINER_NAME}" \
  --network claude-agent-net \
  --cpus 8 \
  --memory 12G \
  --dns 1.1.1.1 \
  -v "${GIT_ROOT}:/workspace" \
  -v "${AGENTS_HOME}:/worktrees" \
  -v "${HOME}/.claude:/root/.claudenew:ro" \
  -v "${HOME}/.claude.json:/root/.claudenew.json:ro" \
  -e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
  -e "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CONTAINER_OAUTH_TOKEN}" \
  claude-agent:wolfi \
  --worktree "${BRANCH}" --task "${TASK}"
```

**Step 3: Confirm launch**
```bash
container list | grep "${CONTAINER_NAME}"
```

## Listing active agents

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
PROJECT_NAME=$(basename "$GIT_ROOT")

# Active containers for this project
container list | grep "${PROJECT_NAME}" || echo "(no active agents)"

# Worktrees on disk
ls -la "${AGENTS_HOME}" 2>/dev/null || echo "(no worktrees yet at $AGENTS_HOME)"
```

Show the user a readable table with both container status and worktree list.

## Reading agent output (context)

`container logs` captures everything the agent prints (Claude's reasoning,
tool calls, results). Use this to pass context back to the user:

```bash
CONTAINER_NAME="${PROJECT_NAME}-${CONTAINER_BRANCH}"

# Last 100 lines (good for summary)
container logs -n 100 "${CONTAINER_NAME}"

# Follow live output (for running agents)
container logs -f "${CONTAINER_NAME}"
```

Read the logs and **summarize the agent's progress** — don't just dump raw output.
Tell the user: what the agent is working on, what it has done, what step it's at.

## Integrating agent work

When an agent finishes, its commits already exist in the **host repo** — the
container volume mount (`-v "${GIT_ROOT}:/workspace"`) means host and container
share the same `.git` directory. The agent's branch is a regular local branch.

**Always use `git merge` to integrate agent work. Never copy files from the
worktree directory.**

```bash
# From the target branch:
git merge <agent-branch>          # e.g. git merge test/shellspec-entrypoint

# Or for multiple agents into a new branch:
git checkout -b <combined-branch>
git merge <agent-branch-1>
git merge <agent-branch-2>
```

> **Note:** The worktree's `.git` file contains a container path
> (`/workspace/.git/worktrees/...`) so `git log` run *from the worktree
> directory on the host* will fail. This does **not** mean the branch is broken
> — verify with `git log <branch>` from the main repo instead.

## Stopping an agent

```bash
container stop "${CONTAINER_NAME}"
```

If the user wants to clean up the worktree too:
```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
git -C "${GIT_ROOT}" worktree remove --force "${AGENTS_HOME}/${BRANCH}"
rm -rf "${AGENTS_HOME}/${BRANCH}"
```

## Apple Container CLI reference (key commands)

```
container run -d --rm --name <n> --network <net> --cpus <n> --memory <n>G \
  --dns <ip> -v <host>:<container> -e KEY=VAL <image> [args...]

container list [--all] [--format json|table] [-q]
container logs [-f] [-n <lines>] <container-id>
container stop [--signal <sig>] [--time <sec>] <container-id>
container network list [--format json|table]
container network create --subnet <cidr> <name>
```

Full docs: https://github.com/apple/container/blob/main/docs/command-reference.md

## Important notes

- **AGENTS_HOME** must point to a persistent path — worktrees persist there after
  the container exits so you can review the agent's work.
- **CLAUDE_CONTAINER_OAUTH_TOKEN** must be set — containers authenticate with this,
  not the host Claude session.
- The image `claude-agent:wolfi` must exist. If not: `cd <git-root>/config && make build`
- Multiple agents run in parallel — each gets a unique container + worktree.
- Branch names with `/` (e.g., `feat/auth`) are valid for git; sanitized for container
  names using `tr '/_ ' '-'` (each separator → single `-`), giving `feat-auth`.
