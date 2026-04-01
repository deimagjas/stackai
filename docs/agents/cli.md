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
            └── agents.py             ← spawn, list, logs, follow, stop
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
