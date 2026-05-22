# End-to-end tests — orchestrator ↔ agent

The E2E tests spawn **real Apple Container CLI containers** and validate the
full round-trip between the orchestrator (the `q` CLI) and an agent running in
a container. They complement — they do not replace — the mocked acceptance
suite: acceptance tests are the fast contract, E2E is the real integration
smoke.

**Location:** `app/cli/tests/e2e/`

## Why opt-in and local-only

The tests need Apple Container CLI (macOS 26+, ARM64), which GitHub Actions
does not have — exactly like the acceptance suite. They are also slow and
billable. So they are gated:

- Collection is guarded by `STACKAI_E2E=1`. Without it, pytest never imports
  the test modules, so the default `uv run pytest` and the `mutmut` suite
  ignore them entirely.
- `make e2e-test` (from `app/cli/`) exports the variable and runs them.
- They are excluded from CI and from `make local-qa` by design.

## Prerequisites

Each test skips itself, with a reason, when a prerequisite is missing.

| Test | Needs |
|---|---|
| both | Apple Container CLI on `PATH`; the bridge network (created automatically) |
| E2E-1 (Claude) | `CLAUDE_CONTAINER_OAUTH_TOKEN` exported; `claude-agent:wolfi` built (`q build`) |
| E2E-2 (PI) | `claude-pi:ubuntu` built (`q pi build`); `mlx_lm.server` reachable (`uv run iac server start`) |

> **Cost:** E2E-1 spends real Claude credits — it runs a live headless agent.
> E2E-2 uses the local model, so it is free but needs the model downloaded and
> the server running.

The PI server URL defaults to `http://localhost:8080/v1/models`; override the
reachability check with `STACKAI_E2E_MLX_URL` if your server listens elsewhere.

## How to run

```bash
cd app/cli
make e2e-test          # STACKAI_E2E=1 uv run pytest tests/e2e -v -m e2e
```

Run a single test:

```bash
STACKAI_E2E=1 uv run pytest tests/e2e/test_claude_agent_e2e.py -v
```

## What each test asserts

Both tests dispatch a deterministic task, wait for the agent to reach a
terminal phase, then assert the orchestrator receives the report through every
channel. Each test runs in an isolated `AGENTS_HOME` (a temp directory) and
tears down its container, worktree and branch afterwards.

### E2E-1 — Claude agent (`test_claude_agent_e2e.py`)

1. `q network`, then `q spawn` with a task that creates `E2E_OK.txt` and commits.
2. `status.json` reaches `phase=completed`, `exit_code=0`, `commits>=1`.
3. The committed file exists in the shared worktree.
4. `q agents status`, `q agents logs` and `q agents summary` surface the
   report (status JSON, persisted log, `[agent:status]` markers).

### E2E-2 — PI agent (`test_pi_agent_e2e.py`)

1. `q pi spawn` against the local `mlx_lm.server` backend (no Claude token).
2. `status.json` reaches `phase=completed` and is tagged `agent_kind=pi`.
3. `q pi status`, `q pi list` and `q pi logs` surface the PI report; `q pi list`
   filters this worktree in by `agent_kind=pi`.

`MAX_PI_AGENTS` enforcement is not E2E-tested — it would need a racy
spawn-while-running attempt; it is covered by the Makefile logic and the mocked
acceptance suite.
