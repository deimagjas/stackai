# spawn-agent — Virtual Agent Coordination

## Overview

`spawn-agent` is a Claude Code skill that turns the host into a **virtual agent coordinator**. Each virtual agent is an Apple Container running Claude in headless mode (`claude -p`) inside an isolated git worktree, and reports its progress through `container logs`.

```
┌─────────────────────────────────────────────────────────────┐
│  Host (coordinator)                                          │
│  Claude Code + spawn-agent skill                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ stackai-     │  │ stackai-     │  │ stackai-     │       │
│  │ feat-oauth2  │  │ test-payment │  │ mutation-api │       │
│  │              │  │              │  │              │       │
│  │ claude -p    │  │ claude -p    │  │ claude -p    │       │
│  │ /worktrees/  │  │ /worktrees/  │  │ /worktrees/  │       │
│  │ feat/oauth2  │  │ test/payment │  │ mutation/api │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         ↑                  ↑                  ↑              │
│         └──────────────────┴──────────────────┘              │
│                  container logs (context)                     │
│                                                              │
│  $AGENTS_HOME/                                               │
│  ├── feat/oauth2/       ← worktree persists post-container   │
│  ├── test/payment-service/                                   │
│  └── mutation/api/                                           │
└─────────────────────────────────────────────────────────────┘
```

### Why worktrees inside the container

Git worktrees must be created from within a context where the repository is accessible. The container mounts the main repo at `/workspace` and the worktrees at `/worktrees`. The `entrypoint.sh` runs `git -C /workspace worktree add /worktrees/<branch>` before launching Claude, ensuring complete isolation between agents.

---

## Prerequisites

### 1. Docker Image

```bash
cd /path/to/project/config
make build
```

Verify it exists:
```bash
container image list | grep "claude-agent.*wolfi"
```

### 2. Environment variables (once in `~/.zshrc` or `~/.bashrc`)

```bash
# Directory where agent worktrees will be stored
export AGENTS_HOME=~/agents          # or any persistent path

# OAuth token for Claude to authenticate inside the container
# ⚠️  Different from your host session token — avoids collisions
export CLAUDE_CONTAINER_OAUTH_TOKEN=<your-oauth-token>
```

> **Why two tokens?** Claude Code uses the host's `~/.claude/` for the interactive session. Containers receive the token via environment variable, preventing two Claude instances from competing for the same session state.

---

## Main Flow

```
1. User asks Claude for a task → skill activates automatically
         │
         ▼
2. Claude verifies AGENTS_HOME and CLAUDE_CONTAINER_OAUTH_TOKEN
         │ (if missing → shows what to export)
         ▼
3. Claude determines the agent type (feature / test / mutation / explore)
   and builds the appropriate prompt
         │
         ▼
4. Claude computes path variables:
   GIT_ROOT       = git rev-parse --show-toplevel
   PROJECT_NAME   = basename $GIT_ROOT
   CONTAINER_NAME = ${PROJECT_NAME}-$(echo $BRANCH | tr '/_ ' '-' | tr A-Z a-z)
         │
         ▼
5. container run -d --rm  ← detached (non-blocking)
   • -v $GIT_ROOT:/workspace          ← full repo (read/write)
   • -v $AGENTS_HOME:/worktrees       ← worktree destination
   • --worktree $BRANCH               → entrypoint creates the worktree
   • --task "$TASK"                   → claude -p "$TASK" in the worktree
         │
         ▼
6. Inside the container (entrypoint.sh):
   a) Copies credentials from host mounts → /root/.claude/
   b) git -C /workspace worktree add /worktrees/$BRANCH -b $BRANCH
   c) cd /worktrees/$BRANCH
   d) Copies credentials to /home/agent/.claude/ + chown agent
   e) su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions -p "$TASK"
   (Claude requires uid != 0 to use --dangerously-skip-permissions)
         │
         ▼
7. Claude in the agent works autonomously:
   reads codebase → implements → commits → exits
         │
         ▼
8. Coordinator can read progress in real time:
   container logs -f ${CONTAINER_NAME}
         │
         ▼
9. On completion: container is removed (--rm), worktree persists in AGENTS_HOME
```

---

## Agent Types and Automatic Prompts

The skill builds the prompt based on the type detected from the user's request:

### `feature` — new functionality

**When**: the user asks to implement something new.

```
You are a senior software engineer. Implement the following in this codebase:
<user description>
Requirements:
- Write clean, tested, production-ready code
- Follow existing conventions (read the codebase first)
- Create a git commit when done with a descriptive message
```

### `test` — unit tests

**When**: the user asks to write or improve tests.

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

### `mutation` — mutation testing

**When**: the user asks for mutation testing or test coverage analysis.

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

### `explore` / general

**When**: any other code task.

```
You are a senior software engineer. Your task:
<user description>
Work autonomously, read the codebase as needed, and commit any changes.
```

---

## Container Naming

The container name is automatically derived from the project and branch:

```
CONTAINER_NAME = <PROJECT_NAME>-<CONTAINER_BRANCH>

where:
  PROJECT_NAME   = basename $(git rev-parse --show-toplevel)
  CONTAINER_BRANCH = echo $BRANCH | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]'
```

| Branch | PROJECT_NAME | CONTAINER_NAME |
|---|---|---|
| `feat/oauth2` | `stackai` | `stackai-feat-oauth2` |
| `test/payment-service` | `stackai` | `stackai-test-payment-service` |
| `mutation/API_v2` | `stackai` | `stackai-mutation-api-v2` |

> **Sanitization rule**: every `/`, `_`, or space is converted to a single `-`, and the result is lowercased. `tr '/_ ' '-'` is used (not `'---'`) to ensure a 1:1 replacement.

---

## Full Example — Feature Agent

### Scenario
We want to implement OAuth2 with JWT in the API, on branch `feat/oauth2`, without touching the `main` branch.

### 1. Invoke the coordinator

```
"Spawn an agent to implement OAuth2 authentication with JWT tokens. Branch: feat/oauth2"
```

The skill activates automatically.

### 2. What Claude executes

```bash
# Variable verification
test -n "$CLAUDE_CONTAINER_OAUTH_TOKEN" || echo "ERROR: export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>"
test -n "$AGENTS_HOME"                  || echo "ERROR: export AGENTS_HOME=<path>"

# Variables
GIT_ROOT=$(git rev-parse --show-toplevel)     # /home/user/projects/stackai
PROJECT_NAME=$(basename "$GIT_ROOT")           # stackai
BRANCH="feat/oauth2"
CONTAINER_BRANCH=$(echo "$BRANCH" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')
# => feat-oauth2
CONTAINER_NAME="${PROJECT_NAME}-${CONTAINER_BRANCH}"
# => stackai-feat-oauth2

# Network (macOS 26+)
container network list --format json 2>/dev/null | grep -q '"claude-agent-net"' \
  || container network create --subnet 192.168.100.0/24 claude-agent-net

# Worktrees directory
mkdir -p "${AGENTS_HOME}"

# Launch agent
TASK="You are a senior software engineer. Implement the following in this codebase:
Implement OAuth2 authentication with JWT tokens in the API.
Requirements:
- Write clean, tested, production-ready code
- Follow existing conventions (read the codebase first)
- Create a git commit when done with a descriptive message"

container run -d --rm \
  --name "stackai-feat-oauth2" \
  --network claude-agent-net \
  --cpus 8 --memory 12G --dns 1.1.1.1 \
  -v "${GIT_ROOT}:/workspace" \
  -v "${AGENTS_HOME}:/worktrees" \
  -v "${HOME}/.claude:/root/.claudenew:ro" \
  -v "${HOME}/.claude.json:/root/.claudenew.json:ro" \
  -e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
  -e "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CONTAINER_OAUTH_TOKEN}" \
  claude-agent:wolfi \
  --worktree "feat/oauth2" --task "${TASK}"

# Confirm
container list | grep "stackai-feat-oauth2"
```

### 3. Monitor progress

```bash
# Last 100 lines (snapshot)
container logs -n 100 stackai-feat-oauth2

# Real time
container logs -f stackai-feat-oauth2
```

Claude summarizes the logs and explains what step the agent is at.

### 4. Result

On completion, the agent will have:
- Created the `feat/oauth2` branch
- Implemented OAuth2 + JWT on the branch
- Made a commit with a descriptive message
- Exited (container automatically removed)

The worktree persists in `$AGENTS_HOME/feat/oauth2/` so you can review the code.

### 5. Review and merge

```bash
# View the agent's commits
git -C "$AGENTS_HOME/feat/oauth2" log --oneline -10

# Diff against main
git -C "$GIT_ROOT" diff main..feat/oauth2 --stat

# Merge if satisfied
git -C "$GIT_ROOT" merge feat/oauth2

# Clean up worktree
git -C "$GIT_ROOT" worktree remove --force "$AGENTS_HOME/feat/oauth2"
rm -rf "$AGENTS_HOME/feat/oauth2"
```

---

## Operations Reference

### List active agents

```
"Show me what agents are currently running"
```

Claude executes:
```bash
container list | grep "${PROJECT_NAME}"
ls -la "${AGENTS_HOME}"
```

### Monitor a specific agent

```
"What is the feat/oauth2 agent doing?"
```

Claude executes `container logs -n 100 stackai-feat-oauth2` and gives you a natural language summary.

### Stop an agent

```
"Stop the feat/oauth2 agent"
```

Claude executes:
```bash
container stop stackai-feat-oauth2
```

Optionally cleans up the worktree if you ask.

### Launch multiple agents in parallel

```
"Spawn three agents: one for OAuth, one for tests on auth, one for mutation testing on payments"
```

Claude launches the three containers in sequence (detached), each with its own branch and prompt.

---

## Apple Container CLI Reference

```
container run -d --rm --name <n> --network <net> --cpus <n> --memory <n>G
             --dns <ip> -v <host>:<container> -e KEY=VAL <image> [args...]

container list [--all] [--format json|table] [-q]
container logs [-f] [-n <lines>] <container-id>
container stop [--signal <sig>] [--time <sec>] <container-id>
container network list [--format json|table]
container network create --subnet <cidr> <name>
```

Full docs: https://github.com/apple/container/blob/main/docs/command-reference.md

---

## Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| `ERROR: export AGENTS_HOME` | Variable not set | `export AGENTS_HOME=~/agents` in `~/.zshrc` |
| `ERROR: export CLAUDE_CONTAINER_OAUTH_TOKEN` | Token not set | `export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>` |
| `Image not found: claude-agent:wolfi` | Image not built | `cd config && make build` |
| `--dangerously-skip-permissions cannot be used with root` | Old image without `agent` user | `cd config && make build` to rebuild |
| Worktree creation failed (branch + dir already exist) | Previous attempt left remnants | `git worktree prune && git branch -D <branch> && rm -rf $AGENTS_HOME/<branch>` |
| Container exits immediately | Error in entrypoint | `container logs <name>` to see the error (without `--rm` to preserve logs) |
| Duplicate container name | Agent already running | `container list` to verify; `container stop <name>` to free it |
