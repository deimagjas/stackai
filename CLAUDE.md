# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

stackai orchestrates parallel Claude Code agents in sandboxed Apple Containers (macOS 26+, ARM64). Each agent runs in its own git worktree for branch-isolated development. Two modes: direct container management (Makefile/CLI) and host-side skill coordination (spawn-agent).

## Build & run

```bash
# Build the production image (ARM64, Wolfi-based)
cd config && make build

# Create the container network (required once)
make network

# Interactive container session
make run

# Spawn a headless agent
make spawn BRANCH=feat/foo TASK="implement feature X"

# Monitor agents
make list-agents
make follow-agent BRANCH=feat/foo
make stop-agent BRANCH=feat/foo

# Cleanup
make clean          # remove image + containers
make clean-network  # remove bridge network
make clean-all      # remove everything
```

### Python CLI (`q` command)

```bash
cd app/cli && uv sync
uv run q build
uv run q spawn --branch feat/foo --task "implement feature X"
uv run q agents list
```

## Testing

```bash
# Python CLI tests (from app/cli/)
cd app/cli && uv sync
uv run pytest -v                    # full suite
uv run pytest tests/test_agents.py  # single module
uv run pytest -k test_spawn         # single test by name

# Linting
uv run ruff check .

# Entrypoint BDD tests (from config/)
cd config && shellspec --shell bash
```

CI runs all of these plus hadolint on both Dockerfiles and an Alpine builder stage compilation check.

## Architecture

- **`config/`** — Container infrastructure: `Dockerfile.wolfi` (production, multi-stage: Rust tool compilation → runtime with Claude CLI, Node, Python), `entrypoint.sh` (credential injection + worktree creation + su-exec privilege drop), `Makefile` (orchestration)
- **`app/cli/`** — Python CLI (`q`) using Typer+Rich that wraps Makefile targets. Entry point registered as `q` in pyproject.toml. Commands delegate to `make` via `utils.run_make()`
- **`.claude/skills/`** — Host-side Claude Code skills for multi-agent orchestration (spawn-agent, spawn-agent-workspace)
- **`docs/agents/`** — All project documentation (container reference, CLI, setup/auth, skill architecture, evals)

### Key concepts

- **Dual-token architecture**: Host uses `CLAUDE_CONTAINER_OAUTH_TOKEN`; inside the container it maps to `CLAUDE_CODE_OAUTH_TOKEN`. Host credentials are mounted read-only and copied (never modified in place).
- **Worktree isolation**: Each agent gets its own git worktree under `$AGENTS_HOME` (default: sibling `.worktrees/` directory). Branches are merge-ready when the agent finishes.
- **Apple Container CLI**: This project uses Apple's container runtime, not Docker. The Makefile targets use `container` commands.

## Documentation

When implementing a new feature, always update the relevant documentation in `docs/`.

- If the feature affects container behavior, image build, or the entrypoint: update `docs/agents/container-agent.md`
- If the feature affects how agents are spawned or monitored: update `docs/agents/spawn-agent-skill.md`
- If the feature adds or changes CLI commands in `app/cli/`: update `docs/agents/cli.md`
- If a new subsystem is introduced with no existing doc, create a new file under the appropriate `docs/` subdirectory

Documentation should reflect the current state of the code. Keep troubleshooting tables and flow descriptions in sync with the actual implementation.

## Skill evals

When modifying any skill under `.claude/skills/`, run its evals locally before considering the change complete. Evals verify that the skill still produces correct outputs across all test scenarios.

```
/skill-creator:skill-creator run evals for the <skill-name> skill at ~/.claude/skills/<skill-name>/
```

See `docs/agents/evals.md` for full details on prerequisites, how to add new evals, and how to interpret results.
