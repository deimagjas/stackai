# q — Python CLI for Container Management

## Overview

`q` is a typed Python CLI (built with [Typer](https://typer.tiangolo.com/)) that wraps the `config/Makefile` targets. It replaces raw `make` invocations with an ergonomic, documented interface.

**Package location:** `app/cli/`
**Entry point:** `q` (installed via `uv`)

---

## Setup

```bash
cd app/cli
uv sync          # installs typer, rich, and the q entry point
uv run q --help  # verify installation
```

---

## Command Reference

### `q build`

Builds the `claude-agent:wolfi` image (no cache).

```bash
q build
q build --image my-image:tag --dockerfile Dockerfile.custom
```

| Option | Default | Description |
|---|---|---|
| `--image` | `claude-agent:wolfi` | Image tag |
| `--dockerfile` | `Dockerfile.wolfi` | Dockerfile to use |

---

### `q network`

Creates the isolated bridge network (`claude-agent-net`). Idempotent — skips if already exists.

```bash
q network
q network --subnet 10.0.0.0/24 --network-name my-net
```

---

### `q run` / `q shell`

Runs an interactive coordinator shell. Hands off the TTY completely via `os.execvp`.

```bash
q run
q run --cpus 4 --memory 8G --name my-coordinator
q shell   # alias for run
```

Requires `CLAUDE_CONTAINER_OAUTH_TOKEN` to be set.

---

### `q spawn`

Spawns a detached headless agent in an isolated git worktree.

```bash
q spawn --branch feat/oauth2 --task "Implement OAuth2 with JWT tokens"
q spawn --branch test/payments --task "Write unit tests for payments module" --cpus 4
```

| Option | Required | Description |
|---|---|---|
| `--branch` | yes | Git branch for the agent worktree |
| `--task` | yes | Task description (prompt for Claude) |
| `--cpus` | no | CPU count override |
| `--memory` | no | Memory limit override (e.g. `8G`) |
| `--image` | no | Image tag override |

Requires `CLAUDE_CONTAINER_OAUTH_TOKEN` to be set.

> **Branch naming:** avoid `/` in branch names — they create nested subdirectories in `$AGENTS_HOME` which the entrypoint cannot handle. Use flat names like `feat-oauth2` instead of `feat/oauth2`.

---

### `q agents` — agent lifecycle sub-commands

#### `q agents list`

Lists active agent containers and worktrees on disk.

```bash
q agents list
```

#### `q agents logs`

Shows snapshot logs for a branch agent.

```bash
q agents logs --branch feat-oauth2
```

#### `q agents follow`

Follows live streaming logs (hands off TTY via `os.execvp`).

```bash
q agents follow --branch feat-oauth2
```

#### `q agents status`

Shows agent status from the persisted `status.json` file. Works even after the
container has exited — reads directly from the worktree filesystem.

```bash
q agents status --branch feat-oauth2
```

Output includes: phase, branch, task, timestamps, duration, exit code, commit count.

#### `q agents summary`

Shows structured lifecycle events (`[agent:status]` markers) for a branch agent.

```bash
q agents summary --branch feat-oauth2
```

#### `q agents stop`

Stops a branch agent container.

```bash
q agents stop --branch feat-oauth2
```

#### Log fallback behavior

When the container no longer exists (agent finished, `--rm` removed it), `logs` and
`follow` automatically fall back to the persisted `.agent/agent.log` in the worktree
directory with a contextual message. This avoids confusing error output.

---

### `q pi` — PI agent lifecycle sub-commands

PI agents are a separate agent class backed by a local `mlx_lm.server`
(managed via `/iac`). They do **not** require `CLAUDE_CONTAINER_OAUTH_TOKEN`
— authentication is local. See [pi-agent.md](./pi-agent.md) for the full
architecture.

#### `q pi build`

Builds the `claude-pi:ubuntu` image (`Dockerfile.pi`).

```bash
q pi build
q pi build --image claude-pi:custom --dockerfile Dockerfile.pi.custom
```

#### `q pi spawn`

Spawns a detached headless PI agent (local LLM backend).

```bash
q pi spawn --branch pi/refactor --task "rename ambiguous helpers"
q pi spawn --branch pi/explore --task "explore the auth module" \
           --cpus 4 --memory 8G \
           --base-url http://10.0.0.5:8080/v1
```

| Option | Required | Description |
|---|---|---|
| `--branch` | yes | Git branch for the PI worktree |
| `--task` | yes | Task description for the PI agent |
| `--cpus` | no | CPU count |
| `--memory` | no | Memory limit (e.g. `3G`) |
| `--image` | no | PI image tag override |
| `--base-url` | no | OpenAI-compatible base URL of the local LLM |

The Makefile enforces **`MAX_PI_AGENTS=1`** by default — `spawn` will refuse
to launch a second PI agent while one is still running. The model + 6 GB
prompt cache leaves little RAM headroom on M-series machines.

#### `q pi list`, `q pi logs`, `q pi follow`, `q pi status`, `q pi stop`

```bash
q pi list                                 # PI agents only
q pi logs   --branch pi/refactor          # snapshot logs
q pi follow --branch pi/refactor          # live logs (TTY hand-off)
q pi status --branch pi/refactor          # status.json (works post-exit)
q pi stop   --branch pi/refactor          # stop the container
```

The list command filters by `agent_kind=pi` in `status.json`, so it
returns only PI worktrees — Claude agent worktrees in the same
`AGENTS_HOME` are excluded.

---

### Cleanup commands

```bash
q clean           # Remove container + image
q clean-network   # Remove bridge network
q clean-all       # Remove image + network
```

---

## How it works

All commands resolve the `config/Makefile` path dynamically:

```
git rev-parse --show-toplevel  →  GIT_ROOT / "config"  →  make -C <path> <target> [VARS]
```

Commands that contact the container daemon (`run`, `spawn`) call `check_token()` which validates `CLAUDE_CONTAINER_OAUTH_TOKEN` is set before invoking make.

TTY-intensive commands (`run`, `shell`, `agents follow`) use `os.execvp` to replace the process entirely, so the terminal is fully handed off with no intermediary.

---

## Package structure

```
app/cli/
├── pyproject.toml                    ← uv project, entry point: q
└── src/
    └── container_cli/
        ├── main.py                   ← registers all commands + agents sub-app
        ├── utils.py                  ← find_git_root, makefile_dir, check_token, run_make
        └── commands/
            ├── build.py              ← build, clean, clean-network, clean-all
            ├── network.py            ← network
            ├── run.py                ← run, shell
            ├── agents.py             ← spawn, list, logs, follow, stop
            └── pi_agents.py          ← pi build/spawn/list/logs/follow/stop/status
```

---

## CLI ↔ Makefile mapping

| CLI command | Makefile target | Notes |
|---|---|---|
| `q build` | `build` | optional `--image`, `--dockerfile` |
| `q network` | `network` | optional `--subnet`, `--network-name` |
| `q run` | `run` | TTY hand-off via `os.execvp` |
| `q shell` | `shell` | alias for run |
| `q spawn` | `spawn` | requires `--branch`, `--task` |
| `q agents list` | `list-agents` | |
| `q agents logs` | `logs-agent` | requires `--branch` |
| `q agents follow` | `follow-agent` | TTY hand-off |
| `q agents stop` | `stop-agent` | requires `--branch` |
| `q clean` | `clean` | |
| `q clean-network` | `clean-network` | |
| `q clean-all` | `clean-all` | |
| `q pi build` | `build-pi` | optional `--image`, `--dockerfile` |
| `q pi spawn` | `spawn-pi` | requires `--branch`, `--task`; no Claude token needed |
| `q pi list` | `list-pi-agents` | filters by `agent_kind=pi` |
| `q pi logs` | `logs-pi-agent` | requires `--branch` |
| `q pi follow` | `follow-pi-agent` | TTY hand-off |
| `q pi stop` | `stop-pi-agent` | requires `--branch` |
| `q pi status` | _(local read)_ | reads `$AGENTS_HOME/<b>/.agent/status.json` |
