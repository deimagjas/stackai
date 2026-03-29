# =============================================================================
# Makefile — Claude Agent (Chainguard Wolfi) · Apple Container CLI
# =============================================================================
#
# Requires: Apple Container CLI  https://github.com/apple/container
# Network targets require macOS 26+
#
# Usage:
#   make build            Build the image (no cache)
#   make network          Create the isolated bridge network
#   make run              Create network (if needed) + run container
#   make shell            Same as run (explicit /bin/bash)
#   make clean            Remove the image
#   make clean-network    Remove the bridge network
#   make clean-all        Remove image + network
#   make help             Show this help
#
# Agent targets (multi-agent mode):
#   make spawn  BRANCH=feat/auth TASK="implement OAuth flow"
#   make list-agents
#   make logs-agent   BRANCH=feat/auth
#   make follow-agent BRANCH=feat/auth
#   make stop-agent   BRANCH=feat/auth
#
# Override any variable at call time, e.g.:
#   make run NAME=my-agent CPUS=4 MEMORY=8G
#
# Host token:
#   Export CLAUDE_CONTAINER_OAUTH_TOKEN in your shell before running.
#   It maps to CLAUDE_CODE_OAUTH_TOKEN inside the container, keeping it
#   isolated from the host Claude Code instance.
#
#   export CLAUDE_CONTAINER_OAUTH_TOKEN=<your-oauth-token>
# =============================================================================

IMAGE      ?= claude-agent:wolfi
DOCKERFILE ?= Dockerfile.wolfi
NAME       ?= qubits-team
NETWORK    ?= claude-agent-net
SUBNET     ?= 192.168.100.0/24
CPUS       ?= 8
MEMORY     ?= 3G

# Agent variables
BRANCH     ?= agent-$(shell date +%s)
TASK       ?= Explore the codebase and report what you find.

# Derived paths
GIT_ROOT      := $(shell git -C $(CURDIR) rev-parse --show-toplevel)
PROJECT_NAME  := $(shell basename $(GIT_ROOT))
# AGENTS_HOME: directory where agent worktrees are stored.
# Set once in your shell profile: export AGENTS_HOME=~/agents
# Falls back to a sibling .worktrees/ next to the project if not set.
AGENTS_HOME   ?= $(shell dirname $(GIT_ROOT))/.worktrees
WORKTREES_DIR := $(AGENTS_HOME)

# Sanitize branch name: each /, _, or space → single -, lowercased
CONTAINER_BRANCH := $(shell echo "$(BRANCH)" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')

# Host env var holding the OAuth token (avoids collision with host Claude instance)
HOST_TOKEN_VAR := CLAUDE_CONTAINER_OAUTH_TOKEN

.PHONY: build network run shell spawn list-agents logs-agent follow-agent stop-agent clean clean-network clean-all help

# ── Build ─────────────────────────────────────────────────────────────────────

build:
	container build --no-cache -f $(DOCKERFILE) -t $(IMAGE) .

# ── Network (macOS 26+) ───────────────────────────────────────────────────────

network:
	@container network list 2>/dev/null | grep -q "^$(NETWORK)" \
		&& echo "[network] $(NETWORK) already exists — skipping" \
		|| container network create --subnet $(SUBNET) $(NETWORK)

# ── Run (interactive coordinator shell) ───────────────────────────────────────

_check-token:
	@test -n "$${$(HOST_TOKEN_VAR)}" \
		|| (echo "[error] $(HOST_TOKEN_VAR) is not set — export it before running" && exit 1)

run: network _check-token
	container run -it --rm \
		--name $(NAME) \
		--network $(NETWORK) \
		--cpus $(CPUS) \
		--memory $(MEMORY) \
		--dns 1.1.1.1 \
		-v $(GIT_ROOT):/workspace \
		-v $(HOME)/.claude:/root/.claudenew:ro \
		-v $(HOME)/.claude.json:/root/.claudenew.json:ro \
		-e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
		-e CLAUDE_CODE_OAUTH_TOKEN=$${$(HOST_TOKEN_VAR)} \
		$(IMAGE)

shell: run

# ── Spawn virtual agent (detached, headless) ──────────────────────────────────
#
# Usage:
#   make spawn BRANCH=feat/auth TASK="implement OAuth flow"
#   make spawn BRANCH=test/auth TASK="write unit tests for the auth module"
#   make spawn BRANCH=mutation/auth TASK="run mutation testing on auth module"

spawn: network _check-token
	@mkdir -p "$(WORKTREES_DIR)"
	@echo "[spawn] Launching agent: $(PROJECT_NAME)-$(CONTAINER_BRANCH)"
	@echo "[spawn] Worktree: $(WORKTREES_DIR)/$(BRANCH)"
	@echo "[spawn] Task: $(TASK)"
	container run -d --rm \
		--name $(PROJECT_NAME)-$(CONTAINER_BRANCH) \
		--network $(NETWORK) \
		--cpus $(CPUS) \
		--memory $(MEMORY) \
		--dns 1.1.1.1 \
		-v $(GIT_ROOT):/workspace \
		-v $(WORKTREES_DIR):/worktrees \
		-v $(HOME)/.claude:/root/.claudenew:ro \
		-v $(HOME)/.claude.json:/root/.claudenew.json:ro \
		-e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
		-e CLAUDE_CODE_OAUTH_TOKEN=$${$(HOST_TOKEN_VAR)} \
		$(IMAGE) \
		--worktree "$(BRANCH)" --task "$(TASK)"
	@echo "[spawn] Agent started. View logs: make logs-agent BRANCH=$(BRANCH)"

# ── Agent monitoring ──────────────────────────────────────────────────────────

list-agents:
	@echo "[agents] Active containers for project '$(PROJECT_NAME)':"
	@container list 2>/dev/null | grep "$(PROJECT_NAME)" || echo "  (none)"
	@echo ""
	@echo "[agents] Worktrees in $(WORKTREES_DIR):"
	@ls -la "$(WORKTREES_DIR)" 2>/dev/null || echo "  (none yet)"

logs-agent:
	container logs $(PROJECT_NAME)-$(CONTAINER_BRANCH)

follow-agent:
	container logs -f $(PROJECT_NAME)-$(CONTAINER_BRANCH)

stop-agent:
	@container stop $(PROJECT_NAME)-$(CONTAINER_BRANCH) 2>/dev/null \
		&& echo "[stop] Agent $(PROJECT_NAME)-$(CONTAINER_BRANCH) stopped." \
		|| echo "[stop] Agent $(PROJECT_NAME)-$(CONTAINER_BRANCH) not found or already stopped."

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	container delete --force $(NAME) 2>/dev/null || true
	container image delete $(IMAGE) 2>/dev/null || true

clean-network:
	container network delete $(NETWORK) 2>/dev/null || true

clean-all: clean clean-network

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Targets:"
	@echo "    build            Build image (no cache)"
	@echo "    network          Create bridge network $(NETWORK) ($(SUBNET))  [macOS 26+]"
	@echo "    run              Create network + run coordinator interactively"
	@echo "    shell            Alias for run"
	@echo "    spawn            Launch detached headless agent (see Agent targets)"
	@echo "    list-agents      List active agent containers"
	@echo "    logs-agent       Show logs for BRANCH agent"
	@echo "    follow-agent     Follow live logs for BRANCH agent"
	@echo "    stop-agent       Stop BRANCH agent"
	@echo "    clean            Remove container + image $(IMAGE)"
	@echo "    clean-network    Remove network $(NETWORK)"
	@echo "    clean-all        Remove image + network"
	@echo ""
	@echo "  Agent targets (examples):"
	@echo "    make spawn BRANCH=feat/auth TASK=\"implement OAuth flow\""
	@echo "    make list-agents"
	@echo "    make logs-agent   BRANCH=feat/auth"
	@echo "    make follow-agent BRANCH=feat/auth"
	@echo "    make stop-agent   BRANCH=feat/auth"
	@echo ""
	@echo "  Variables (override with make <target> VAR=value):"
	@printf "    %-20s %s\n" "IMAGE"          "$(IMAGE)"
	@printf "    %-20s %s\n" "NAME"           "$(NAME)"
	@printf "    %-20s %s\n" "NETWORK"        "$(NETWORK)"
	@printf "    %-20s %s\n" "SUBNET"         "$(SUBNET)"
	@printf "    %-20s %s\n" "CPUS"           "$(CPUS)"
	@printf "    %-20s %s\n" "MEMORY"         "$(MEMORY)"
	@printf "    %-20s %s\n" "BRANCH"         "$(BRANCH)"
	@printf "    %-20s %s\n" "PROJECT_NAME"   "$(PROJECT_NAME)"
	@printf "    %-20s %s\n" "GIT_ROOT"       "$(GIT_ROOT)"
	@printf "    %-20s %s\n" "AGENTS_HOME"    "$(AGENTS_HOME)"
	@printf "    %-20s %s\n" "WORKTREES_DIR"  "$(WORKTREES_DIR)"
	@echo ""
	@echo "  Required host env vars:"
	@echo "    export $(HOST_TOKEN_VAR)=<your-oauth-token>"
	@echo "    export AGENTS_HOME=<path>   # e.g. ~/agents (fallback: sibling .worktrees/)"
	@echo ""
