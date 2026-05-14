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
┌──────────────────────────────────────────────────────────────────────┐
│ Host (macOS 26, Apple Silicon)                                       │
│                                                                      │
│  ┌─────────────────┐                                                 │
│  │ iac CLI         │   mlx_lm.server (Gemma-4-26b, 4-bit MLX)        │
│  │ uv run iac      │──▶ 0.0.0.0:8080 (OpenAI-compatible)             │
│  │ server start    │                                                 │
│  └─────────────────┘                                                 │
│           ▲                                                          │
│           │ HTTP                                                     │
│           │ http://192.168.100.1:8080/v1  (bridge gateway IP)        │
│           │                                                          │
│  ┌────────┴─────────────────────────────────────────┐                │
│  │ Apple Container: claude-pi:ubuntu                │                │
│  │ (Ubuntu 26.04, linux/arm64, kernel 7.x)          │                │
│  │                                                  │                │
│  │   pi -p "<task>" --model local/<model_id>        │                │
│  │     │                                            │                │
│  │     ▼                                            │                │
│  │   ~/.pi/agent/models.json (generated at startup) │                │
│  │     provider "local" → baseUrl PI_BASE_URL       │                │
│  └──────────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

The PI container does NOT carry its own model. It reaches the host's
`mlx_lm.server` via the **gateway IP** of the bridge network created by
Apple Container CLI (`192.168.100.1` for the default
`192.168.100.0/24` subnet).

### Why not `host.containers.internal`?

Apple Container CLI does **not** implement `host.containers.internal`
(see [apple/container#346](https://github.com/apple/container/issues/346)).
DNS lookups for that hostname either fail immediately or time out. The
workaround is to use the bridge gateway IP, which the host owns. If you
override the default subnet via `make network SUBNET=10.20.0.0/24`,
remember to also override `PI_BASE_URL` accordingly
(`make spawn-pi PI_BASE_URL=http://10.20.0.1:8080/v1 …`).

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

## The `pi` CLI and `models.json`

The PI container ships the [pi-coding-agent](https://pi.dev/) (`pi` CLI)
installed via `npm install -g @earendil-works/pi-coding-agent`. Headless
invocation: `pi -p "<prompt>" --model <provider>/<model_id>`.

`entrypoint-pi.sh` generates `~/.pi/agent/models.json` on every start
from these env vars:

| Env var | Purpose | Default |
|---|---|---|
| `PI_BASE_URL` | OpenAI-compatible base URL of the local server | `http://192.168.100.1:8080/v1` |
| `PI_MODEL_ID` | Model id served by `mlx_lm.server` (also the `id` field in `/v1/models`) | `mlx-community/gemma-4-26b-a4b-it-4bit` |
| `PI_PROVIDER_NAME` | Provider key in `models.json` | `local` |

Generated file:

```json
{
  "providers": {
    "local": {
      "baseUrl": "http://192.168.100.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "none",
      "compat": { "supportsDeveloperRole": false },
      "models": [ { "id": "mlx-community/gemma-4-26b-a4b-it-4bit" } ]
    }
  }
}
```

`compat.supportsDeveloperRole: false` is required because `mlx_lm.server`
does not understand OpenAI's `developer` role — pi sends a regular `system`
message instead.

### Discipline preamble (every task is wrapped)

Local models follow instructions much more literally than Claude.
`entrypoint-pi.sh` prepends a structural preamble to **every** task before
invoking `pi -p`, regardless of how the orchestrator phrased it. The model
actually sees:

```
You are running inside a git worktree at <cwd>. Every file path in this task
must be interpreted relative to that directory — never use absolute paths
beginning with /workspace or any other absolute prefix.

Rules:
1. Modify ONLY the files explicitly named in the task. Do not create test
   files, documentation, or auxiliary files unless the task asks for them.
2. After making your changes you MUST run, in this exact order:
       git add -A
       git commit -m "<conventional-commits message describing the change>"
       git log -1 --oneline
   Include that last "git log -1 --oneline" line at the end of your response.
3. If you cannot complete the task, DO NOT commit. Briefly explain why instead.

Task:
<your original --task string>
```

This is structural, not advisory — every PI agent run inherits these rules,
so a user spawning directly via `make spawn-pi TASK="..."` still gets them.

### Sampling defaults

The iac CLI starts `mlx_lm.server` with sampling parameters tuned for
coding tasks (low temperature, narrow nucleus). Override if needed:

| Parameter | Default | Override |
|---|---|---|
| `temp` | `0.2` | `uv run iac server start --temp 0.4` |
| `top_p` | `0.9` | `uv run iac server start --top-p 0.95` |

Pi-coding-agent does **not** send `temperature` or `top_p` on per-request
basis (its `models.json` schema doesn't expose them, nor does its CLI), so
the server defaults are what every PI agent actually uses. Lowering temp
markedly reduces the "model invents extra files" failure mode observed
during the format_bytes test.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `spawn-pi` fails with `MAX_PI_AGENTS=1 reached` | Another PI agent is still running | `make stop-pi-agent BRANCH=<the-old-one>` |
| Container starts but PI agent immediately exits with HTTP error | Local server not running | `uv run iac server status` then `iac server start` |
| Container can't reach `192.168.100.1:8080` | Custom `SUBNET` or post-restart Apple Container bug | Pass `--base-url http://<your-gateway-ip>:8080/v1` to `q pi spawn`, or `make network SUBNET=192.168.100.0/24` to reset to the default |
| `pi` errors with "model not found" | `PI_MODEL_ID` does not match what mlx_lm.server reports at `/v1/models` | `curl http://localhost:8080/v1/models` on the host, then `q pi spawn --model-id <id>` |
| `iac server start` says "already running" but `status` shows stopped | Stale PID file | `rm ~/.iac/server.pid && uv run iac server start` |
| Connection from container hangs indefinitely after macOS restart | Known Apple Container CLI bug — bridge gateway not always reachable post-restart | `container network delete claude-agent-net && make network` |
| First curl from container right after `iac server start` times out, but localhost works | Warm-up gap — `mlx_lm.server` accepts on `127.0.0.1:8080` before the bridge IP is fully reachable (the model still loading into RAM) | Wait ~5-15 s after `iac server status` first reports reachable; or curl from the container until success before spawning the PI agent |

## Why Ubuntu 26.04 (not Chainguard Wolfi)

The PI image targets a distribution that ships **Linux kernel 7.x** for
better `io_uring` and memory-accounting behaviour under sustained LLM
streaming. Chainguard Wolfi remains the right base for Claude agents
(smaller attack surface, faster pulls) — but it lags slightly on kernel
versions. Each agent class can choose the base that fits its workload.
