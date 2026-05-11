# PI Agent (local mlx_lm backend)

PI agents are a **second class of agent** in stackai, complementary to the
default Claude agents documented in [container-agent.md](./container-agent.md).
They use the [pi.dev](https://pi.dev/) SDK as their intelligence layer,
backed by a **local `mlx_lm.server`** running on the host (managed from
`/iac`) — no Anthropic API calls.

## When to use a PI agent

| Scenario | Use |
|---|---|
| You want agent help on a long-running, exploratory task without spending Claude credits | PI agent |
| Air-gapped or offline machine | PI agent |
| Task requires frontier reasoning (large refactors, security review) | Claude agent |
| You haven't installed `mlx_lm` or don't have a model downloaded | Claude agent |

## Architecture at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│ Host (macOS, Apple Silicon)                                      │
│                                                                  │
│  ┌─────────────────┐                                             │
│  │ iac CLI         │   mlx_lm.server (Gemma-4-26b-4bit, 4-bit)   │
│  │ uv run iac      │──▶ 0.0.0.0:8080 (OpenAI-compatible)          │
│  │ server start    │                                             │
│  └─────────────────┘                                             │
│                                                                  │
│  ┌──────────────────────────────────────────┐                    │
│  │ Apple Container: claude-pi:ubuntu        │                    │
│  │ (Ubuntu 26.04, linux/arm64, kernel 7.x)  │                    │
│  │                                          │                    │
│  │   pi agent run --task "..."              │                    │
│  │     │                                    │                    │
│  │     ▼                                    │                    │
│  │   PI_BASE_URL=http://host.containers     │                    │
│  │     .internal:8080/v1                    │                    │
│  └──────────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

The PI container does NOT carry its own model. It hits the host's
`mlx_lm.server` via the well-known DNS name `host.containers.internal`
exposed by Apple Container's bridge network.

## Open/Closed extension model

Existing Claude agent infrastructure is **not modified** to add PI agents.
Every piece is additive:

| Component | Existing (Claude) | New (PI) |
|---|---|---|
| Image | `claude-agent:wolfi` | `claude-pi:ubuntu` |
| Dockerfile | `config/Dockerfile.wolfi` | `config/Dockerfile.pi` |
| Entrypoint | `config/entrypoint.sh` | `config/entrypoint-pi.sh` |
| Makefile targets | `spawn`, `list-agents`, `stop-agent`, … | `spawn-pi`, `list-pi-agents`, `stop-pi-agent`, … |
| CLI command | `q spawn`, `q agents …` | `q pi spawn`, `q pi …` |
| Skill | `spawn-agent` (Claude block) | same skill, dedicated **PI agents** section |

Adding more agent classes in the future (e.g. a different local backend)
follows the same pattern — a new Dockerfile, a new entrypoint, a new
Makefile section, a new CLI module.

## Setup (one-time)

```bash
# 1) Sync the iac project
cd iac && uv sync

# 2) Start the local model server (downloads on first run; takes minutes)
uv run iac server start
uv run iac server status     # should report phase=running

# 3) Build the PI container image
cd ../config && make build-pi
```

## Spawning a PI agent

Preferred (via the CLI wrapper):

```bash
q pi spawn --branch pi/refactor --task "rename ambiguous helpers in src/utils.py"
```

Equivalent direct Makefile call:

```bash
cd config && make spawn-pi \
    BRANCH=pi/refactor TASK="rename ambiguous helpers in src/utils.py"
```

The container is detached, runs to completion, and removes itself with `--rm`.
The branch worktree (and its `.agent/status.json` + `.agent/agent.log`) persists
under `$AGENTS_HOME/pi/refactor/` for review.

## Memory safety — `MAX_PI_AGENTS=1`

The default model (Gemma-4-26b, 4-bit) + 6 GB prompt cache leaves little RAM
headroom on M-series machines. The `spawn-pi` target counts running PI
containers and refuses to launch a new one if it would exceed
`MAX_PI_AGENTS` (default `1`).

To override (only if you know your machine can absorb the load):

```bash
make spawn-pi MAX_PI_AGENTS=2 BRANCH=pi/second TASK="..."
```

## Monitoring and lifecycle

| Action | CLI | Makefile |
|---|---|---|
| List active PI agents | `q pi list` | `make list-pi-agents` |
| Live logs | `q pi follow --branch <b>` | `make follow-pi-agent BRANCH=<b>` |
| Status JSON | `q pi status --branch <b>` | `make status-pi-agent BRANCH=<b>` |
| Stop | `q pi stop --branch <b>` | `make stop-pi-agent BRANCH=<b>` |
| Saved logs (post-exit) | reads `$AGENTS_HOME/<b>/.agent/agent.log` | same |

The `status.json` written by `entrypoint-pi.sh` includes
`"agent_kind": "pi"`, which `list-pi-agents` uses to filter PI worktrees
from regular Claude worktrees that share the same `AGENTS_HOME`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `spawn-pi` fails with `MAX_PI_AGENTS=1 reached` | Another PI agent is still running | `make stop-pi-agent BRANCH=<the-old-one>` |
| Container starts but PI agent immediately exits with HTTP error | Local server not running | `uv run iac server status` then `iac server start` |
| Container can't resolve `host.containers.internal` | Bridge gateway differs in your network | `q pi spawn --base-url http://192.168.100.1:8080/v1 …` (use the gateway IP of `claude-agent-net`) |
| `iac server start` says "already running" but `status` shows stopped | Stale PID file | `rm ~/.iac/server.pid && uv run iac server start` |

## Why Ubuntu 26.04 (not Chainguard Wolfi)

The PI image targets a distribution that ships **Linux kernel 7.x** for
better `io_uring` and memory-accounting behaviour under sustained LLM
streaming. Chainguard Wolfi remains the right base for Claude agents
(smaller attack surface, faster pulls) — but it lags slightly on kernel
versions. Each agent class can choose the base that fits its workload.
