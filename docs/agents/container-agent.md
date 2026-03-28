# claude-agent:wolfi Image — Dockerfile and Makefile

## Overview

`claude-agent:wolfi` is an ARM64 (Apple Silicon M4) image built on Chainguard Wolfi. It is specifically designed to run headless instances of Claude Code in Apple Containers, with support for parallel multi-agent operation.

**Why Wolfi and not Alpine:**
Alpine uses the `musl` library, and the Claude binary ≥ 2.1.63 requires `posix_getdents`, a symbol exclusive to `glibc`. Wolfi is glibc-based with a footprint comparable to Alpine (~5 MB base), without the musl incompatibilities.

---

## Dockerfile.wolfi — Stage-by-stage explanation

### Stage 1: `builder` (Rust tool compilation)

```dockerfile
FROM --platform=linux/arm64 cgr.dev/chainguard/rust:latest-dev AS builder
```

Compiles CLI productivity tools written in Rust:

| Tool | Purpose | Replaces |
|---|---|---|
| `rg` (ripgrep) | Ultra-fast text search | `grep` |
| `fd` (fd-find) | File search | `find` |
| `bat` | Cat with syntax highlighting | `cat` |
| `eza` | Modern file listing | `ls` |
| `dust` | Disk usage visualization | `du` |
| `procs` | Modern process listing | `ps` |
| `btm` (bottom) | System monitor | `top` |

The compiled binaries are copied to stage 2, keeping the final image clean.

### Stage 2: `runtime` (final image)

```dockerfile
FROM --platform=linux/arm64 cgr.dev/chainguard/wolfi-base:latest AS runtime
```

**Installed system packages:**

```
bash, busybox, curl, wget        ← base utilities
git, git-lfs                     ← version control
openssh-client, ca-certificates  ← secure connectivity
jq, unzip, gzip                  ← data processing
tmux                             ← terminal multiplexer
gh                               ← GitHub CLI
nodejs-22, npm                   ← JavaScript runtime
python-3.13, py3-pip             ← Python runtime
```

**Additional tools installed:**

```
claude          ← Claude Code CLI (via official install.sh)
opencode        ← OpenCode AI CLI
openspec        ← @fission-ai/openspec (global npm)
```

**Configured environment variables:**

```dockerfile
LANG=C.UTF-8
LC_ALL=C.UTF-8
TERM=xterm-256color
PATH=/root/.local/bin:/usr/local/bin:$PATH
CLAUDE_CODE_DISABLE_AUTOUPDATE=1   ← prevents auto-updates in containers
BAT_PAGER=""
BAT_STYLE="numbers,changes,header"
```

**Rust aliases** (configured in `/etc/profile.d/rust-aliases.sh`):

```bash
alias grep='rg --smart-case --follow'
alias find='fd --follow'
alias cat='bat --paging=never'
alias ls='eza'
alias ll='eza -la --git'
alias du='dust'
alias ps='procs'
alias top='btm'
```

**Global git configuration:**

```bash
git config --global init.defaultBranch main
git config --global core.editor "true"      # no-op editor (headless)
git config --global advice.detachedHead false
```

---

## entrypoint.sh — Operating modes

The entrypoint supports two modes, selected by the arguments passed to the container.

### Interactive mode (default)

```bash
container run -it claude-agent:wolfi
# or
container run -it claude-agent:wolfi /bin/bash --login
```

**Flow:**
1. Copies credentials: `~/.claudenew.json` → `~/.claude.json` and `~/.claudenew/` → `~/.claude/`
2. Starts an interactive bash shell with the full profile loaded

### Headless agent mode

```bash
container run -d --rm claude-agent:wolfi \
  --worktree "feat/oauth2" \
  --task "Implement OAuth2 with JWT tokens..."
```

**Entrypoint arguments:**

| Argument | Description |
|---|---|
| `--worktree <branch>` | Name of the branch/worktree to create |
| `--task "<prompt>"` | Prompt for Claude in headless mode |
| `--project <name>` | (optional) Project name |

**Flow:**
1. Copies credentials from host mounts
2. `git -C /workspace worktree add /worktrees/<branch> -b <branch>`
   - If the branch already exists: `git worktree add /worktrees/<branch> <branch>`
3. `cd /worktrees/<branch>`
4. `claude --dangerously-skip-permissions -p "<task>"`

**Why `--dangerously-skip-permissions`:** In headless mode there is no interactive user to approve permissions. The container is a sandboxed environment with access only to the mounted worktree, so it is safe to skip confirmations.

**Why run as `agent` (non-root):** Claude CLI blocks `--dangerously-skip-permissions` when the process runs as `root` (uid 0). The entrypoint uses `su-exec` to drop to the `agent` user before executing Claude.

IMPORTANT: **Why the worktree is created inside the container:** Git needs access to the repository to register the worktree in `.git/worktrees/`. Since the repo is mounted at `/workspace` inside the container, the worktree must be created from there. If it were created directly from the host, the path registered in git would be the host path (`/Users/...`), which would not exist inside the container.

---

## Makefile — Target reference

### Configurable variables

| Variable | Default | Description |
|---|---|---|
| `IMAGE` | `claude-agent:wolfi` | Docker image name |
| `DOCKERFILE` | `Dockerfile.wolfi` | Dockerfile to use |
| `NAME` | `qubits-team` | Base name for the interactive container |
| `NETWORK` | `claude-agent-net` | Agent bridge network |
| `SUBNET` | `192.168.100.0/24` | Network CIDR |
| `CPUS` | `8` | CPUs allocated to each container |
| `MEMORY` | `12G` | RAM allocated to each container |
| `BRANCH` | `agent-<timestamp>` | Agent branch to spawn |
| `TASK` | `Explore the codebase...` | Agent task |
| `AGENTS_HOME` | `<parent-of-git-root>/.worktrees` | Fallback if not in env |

**Automatically derived variables:**

```makefile
GIT_ROOT      := $(shell git -C $(CURDIR) rev-parse --show-toplevel)
PROJECT_NAME  := $(shell basename $(GIT_ROOT))
AGENTS_HOME   ?= $(shell dirname $(GIT_ROOT))/.worktrees   # fallback
WORKTREES_DIR := $(AGENTS_HOME)
CONTAINER_BRANCH := $(shell echo "$(BRANCH)" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')
```

### Targets

#### `make build`
Builds the image without cache.
```bash
make build
# equivalent to: container build --no-cache -f Dockerfile.wolfi -t claude-agent:wolfi .
```

#### `make network`
Creates the bridge network `claude-agent-net` if it does not exist. Requires macOS 26+.
```bash
make network
```

#### `make run` / `make shell`
Launches the container in interactive mode (coordinator or development session).
```bash
make run
make run NAME=my-agent CPUS=4 MEMORY=8G
```
Requires `CLAUDE_CONTAINER_OAUTH_TOKEN` to be exported.

#### `make spawn`
Launches a virtual agent in detached (headless) mode. **The main target for multi-agent.**
```bash
make spawn BRANCH=feat/oauth2 TASK="Implement OAuth2 with JWT"
make spawn BRANCH=test/auth TASK="Write unit tests for auth module"
make spawn BRANCH=mutation/payments TASK="Run mutation testing on payment service"
```
- Creates `$AGENTS_HOME` if it does not exist
- Launches container named `${PROJECT_NAME}-${CONTAINER_BRANCH}`
- Shows how to view logs upon completion

#### `make list-agents`
Lists active project containers and worktrees on disk.
```bash
make list-agents
```

#### `make logs-agent BRANCH=<branch>`
Shows agent logs (snapshot).
```bash
make logs-agent BRANCH=feat/oauth2
```

#### `make follow-agent BRANCH=<branch>`
Follows agent logs in real time.
```bash
make follow-agent BRANCH=feat/oauth2
```

#### `make stop-agent BRANCH=<branch>`
Stops the agent.
```bash
make stop-agent BRANCH=feat/oauth2
```

#### `make clean`
Removes the container and the image. Does not affect worktrees.
```bash
make clean
```

#### `make clean-network`
Removes the bridge network.
```bash
make clean-network
```

#### `make clean-all`
Removes image and network.
```bash
make clean-all
```

---

## Host environment variable requirement

```bash
# Required for make run, make spawn
export CLAUDE_CONTAINER_OAUTH_TOKEN=<your-oauth-token>

# Recommended (fallback if not set: dirname(GIT_ROOT)/.worktrees)
export AGENTS_HOME=~/agents
```

**Why `CLAUDE_CONTAINER_OAUTH_TOKEN` and not `CLAUDE_CODE_OAUTH_TOKEN`:**
The Makefile maps `CLAUDE_CONTAINER_OAUTH_TOKEN` from the host to `CLAUDE_CODE_OAUTH_TOKEN` inside the container. This prevents the container from reading the host session token, keeping sessions isolated.

---

## Build instructions

### Standard build

```bash
cd /path/to/project/config
export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>
make build
```

The build may take several minutes the first time (compiles 7 Rust crates).

### Fast build (reuse cache)

Edit the Makefile and remove `--no-cache`:
```makefile
build:
    container build -f $(DOCKERFILE) -t $(IMAGE) .   # without --no-cache
```

### Verify image

```bash
container image list | grep "claude-agent.*wolfi"
container run --rm claude-agent:wolfi claude --version
```

---

## Bridge network (macOS 26+)

The `claude-agent-net` network (CIDR `192.168.100.0/24`) allows containers to communicate with each other and access the internet via DNS `1.1.1.1` (Cloudflare).

```bash
# Create
container network create --subnet 192.168.100.0/24 claude-agent-net

# List
container network list

# Inspect
container network inspect claude-agent-net

# Remove
container network delete claude-agent-net
```

`make network` performs the create idempotently (does not fail if it already exists).

---

## Credential flow

```
Host                              Container
────────────────────────────────────────────────────────
~/.claude/        ──(ro mount)──→ /root/.claudenew/
~/.claude.json    ──(ro mount)──→ /root/.claudenew.json
                                         │
                                  entrypoint.sh
                                  cp -r .claudenew/ → .claude/
                                  cp .claudenew.json → .claude.json
                                         │
                                  Claude Code uses /root/.claude/
                                  (read/write inside the container)

CLAUDE_CONTAINER_OAUTH_TOKEN  ──(env var)──→ CLAUDE_CODE_OAUTH_TOKEN
```

The mounts are **read-only** from the host to prevent the container from modifying the original credentials. The entrypoint makes a local copy so Claude can write to its configuration directory without affecting the host.

---

## Non-root user for headless mode

Claude CLI blocks `--dangerously-skip-permissions` when the process runs as `root` (uid 0). The image includes an `agent` user (non-root) for headless mode.

### Image changes

```dockerfile
# su-exec: privilege drop with exec semantics (Docker standard)
RUN apk add --no-cache su-exec

# agent user (non-root)
RUN addgroup -S agent \
    && adduser -S -G agent -h /home/agent -s /bin/bash agent \
    && ln -sf /root/.local/bin/claude /usr/local/bin/claude
```

### Credential flow for headless mode

```
/root/.claude/         (copied by entrypoint from host mount)
       │
       └─► /home/agent/.claude/   (copied + chown → agent)
                  │
           su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions -p "..."
```

The entrypoint:
1. Copies credentials to `/root/.claude/` (as usual)
2. Also copies them to `/home/agent/.claude/` with `chown agent`
3. Runs `chown agent` on the worktree
4. Executes `su-exec agent` to drop to non-root uid before calling Claude

### Why `su-exec` and not `su` or `runuser`

`su-exec` performs a direct `execvp` (replaces the process, does not create a subshell). This preserves signals, the PID, and avoids the overhead of an additional shell. It is the standard for Docker container entrypoints.

---

## Security notes

- Containers run with `--rm` (ephemeral) — they do not persist state outside the worktree
- Credentials are mounted read-only from the host
- `CLAUDE_CODE_DISABLE_AUTOUPDATE=1` prevents Claude from downloading updates inside the container
- Each container has access only to the repo mounted at `/workspace` and `$AGENTS_HOME` at `/worktrees`
- `--dangerously-skip-permissions` is safe in this context because the accessible filesystem is limited to the mounted volumes
- Headless mode runs as the `agent` user (non-root) by design

---

## Container Strategy: Production vs CI

This project uses two different container strategies depending on the environment:

### Production (local development)

- **Runtime:** Apple Container CLI
- **Dockerfile:** `Dockerfile.wolfi` (ARM64, Chainguard Wolfi)
- **Architecture:** `linux/arm64` (Apple Silicon)
- **C library:** `glibc`

The production image is built with Chainguard Wolfi, a hardened, minimal Linux distribution that uses `glibc`. This is required because Claude Code >= 2.1.63 depends on `posix_getdents`, a POSIX syscall wrapper that `musl` (the C library used by Alpine) does not provide. Wolfi provides `glibc` compatibility with a footprint comparable to Alpine, making it the ideal base for running Claude Code in containers.

Apple Container CLI is used locally to run containers natively on Apple Silicon (ARM64) with low overhead and tight macOS integration (shared networking, volume mounts, bridge networks on macOS 26+).

### CI (GitHub Actions)

- **Runtime:** Docker
- **Dockerfile:** `Dockerfile` (Alpine-based)
- **Architecture:** `linux/amd64`
- **Purpose:** Build validation and testing only

GitHub Actions runners are `amd64` Linux machines. Apple Container CLI is not available in this environment — it is a macOS-only tool tied to the Apple Virtualization framework. Therefore, CI uses standard Docker with the Alpine-based `Dockerfile` for build validation.

The Alpine CI image is sufficient for verifying that the Dockerfile syntax is correct, dependencies resolve, and the build completes successfully. It is **not** used to run Claude Code headless agents — that is exclusively done via the Wolfi image on local Apple Silicon machines.

### Summary

| Aspect | Production (local) | CI (GitHub Actions) |
|---|---|---|
| Container runtime | Apple Container CLI | Docker |
| Dockerfile | `Dockerfile.wolfi` | `Dockerfile` (Alpine) |
| Architecture | `linux/arm64` | `linux/amd64` |
| Base image | Chainguard Wolfi (glibc) | Alpine (musl) |
| Purpose | Run headless Claude agents | Build validation |
| Claude Code compatible | Yes (`glibc` + `posix_getdents`) | No (musl lacks `posix_getdents`) |
