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
  --memory 3G \
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

## Reading agent output

Agents persist structured monitoring data in the worktree at
`${AGENTS_HOME}/<branch>/.agent/`. Use the right source for each question:

### Quick status (preferred for "what is agent X doing?")

```bash
# Read status.json — works even after container exits
cat "${AGENTS_HOME}/${BRANCH}/.agent/status.json" 2>/dev/null
```

Returns JSON with phase, branch, task, timestamps, exit code, and commit count.
Phases: `starting` → `working` → `completed` | `errored`.

### Structured lifecycle events

```bash
CONTAINER_NAME="${PROJECT_NAME}-${CONTAINER_BRANCH}"

# From live container
container logs "${CONTAINER_NAME}" 2>/dev/null | grep '^\[agent:'

# From persisted logs (after container exits)
grep '^\[agent:' "${AGENTS_HOME}/${BRANCH}/.agent/agent.log" 2>/dev/null
```

### Full logs

```bash
# Live container (while running)
container logs -n 100 "${CONTAINER_NAME}"
container logs -f "${CONTAINER_NAME}"

# Persisted logs (after container exits)
tail -100 "${AGENTS_HOME}/${BRANCH}/.agent/agent.log"
```

### Decision flow

- **"What is agent X doing?"** → read `status.json` (instant, always works)
- **"What did agent X do?"** → read `agent.log` (persisted, works post-exit)
- **"Show me live output"** → `container logs -f` (only while running)

Read the logs and **summarize the agent's progress** — don't just dump raw output.
Tell the user: what the agent is working on, what it has done, what step it's at.

**Important:** When the container is gone (agent finished), do NOT attempt
`container logs` — it will fail. Use the persisted files in `.agent/` instead.

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

## PI agents (local mlx_lm backend)

PI agents are a **separate class of agent** that use the pi.dev SDK with a
LOCAL mlx_lm.server (managed via `/iac`) as their OpenAI-compatible backend,
instead of the Anthropic cloud API. They are useful when you want agent work
without consuming Claude API credits, or when the task is well-served by a
local Gemma-class model.

### When to use a PI agent (detection)

Use a PI agent when the user says any of:
- "spawn a PI agent" / "lanza un agente PI"
- "use the local model" / "local LLM"
- "use mlx_lm" / "use the local server"
- "no Claude credits" / "without using the API"

Otherwise, default to a regular Claude agent.

### Required setup (one-time)

```bash
# 1. Build the PI image
cd <git-root>/config && make build-pi

# 2. Start the local model server (from /iac)
cd <git-root>/iac && uv sync && uv run iac server start
uv run iac server status   # verify it is reachable
```

### Spawning a PI agent

PI agents do NOT need `CLAUDE_CONTAINER_OAUTH_TOKEN`. They authenticate
against the local server via `PI_BASE_URL` (default
`http://192.168.100.1:8080/v1` — the **gateway IP** of the default bridge
subnet; `host.containers.internal` is NOT implemented in Apple Container
CLI, see apple/container#346).

Preferred: use the CLI wrapper.

```bash
q pi spawn --branch pi/refactor --task "rename ambiguous helpers"
```

Equivalent Makefile invocation:

```bash
cd <git-root>/config && make spawn-pi \
    BRANCH=pi/refactor TASK="rename ambiguous helpers"
```

Container name pattern: `<project>-pi-<sanitized-branch>` (note the
`-pi-` segment that distinguishes them from Claude agents).

If the user customised the bridge subnet, pass `--base-url`:

```bash
q pi spawn --branch pi/x --task "..." --base-url http://<gateway-ip>:8080/v1
```

### Memory ceiling — MAX_PI_AGENTS=1

The model + 6 GB prompt cache leaves little RAM headroom on Apple Silicon.
The Makefile enforces `MAX_PI_AGENTS=1` by default — `spawn-pi` will refuse
to launch a second PI agent while one is still running. If the user asks
for multiple PI agents in parallel, **warn them** and recommend stopping
the existing one first.

### Listing, monitoring, stopping PI agents

```bash
q pi list                              # only PI agents
q pi follow --branch pi/refactor       # live logs
q pi status --branch pi/refactor       # status.json from worktree
q pi stop   --branch pi/refactor       # stop the container
```

The status.json for PI agents includes `"agent_kind": "pi"`, used to filter
PI worktrees from Claude worktrees in `list-pi-agents`.

### Important — do not mix targets

- Use `spawn-pi` / `q pi spawn` for PI agents — never the regular `spawn`.
- Use `stop-pi-agent` / `q pi stop` for PI agents — never `stop-agent`.
- The two agent classes share `AGENTS_HOME` and the bridge network, but
  their containers, images, and entrypoints are independent.

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
