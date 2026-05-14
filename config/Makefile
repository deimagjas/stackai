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

.PHONY: build network run shell spawn list-agents logs-agent follow-agent stop-agent status-agent summary-agent clean clean-network clean-all help \
        build-pi spawn-pi list-pi-agents logs-pi-agent follow-pi-agent status-pi-agent stop-pi-agent clean-pi

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
	@if [ -d "$(WORKTREES_DIR)" ]; then \
		for dir in $(WORKTREES_DIR)/*/; do \
			[ -d "$$dir" ] || continue; \
			branch=$$(basename "$$dir"); \
			status_file="$$dir/.agent/status.json"; \
			if [ -f "$$status_file" ] && command -v jq >/dev/null 2>&1; then \
				phase=$$(jq -r '.phase // "unknown"' "$$status_file" 2>/dev/null || echo "unknown"); \
				printf "  %-30s %s\n" "$$branch" "$$phase"; \
			else \
				printf "  %-30s %s\n" "$$branch" "(no status)"; \
			fi; \
		done; \
	else \
		echo "  (none yet)"; \
	fi

logs-agent:
	@container logs $(PROJECT_NAME)-$(CONTAINER_BRANCH) 2>/dev/null \
		|| { \
			LOG_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/agent.log"; \
			if [ -f "$$LOG_FILE" ]; then \
				echo "[logs] Container $(PROJECT_NAME)-$(CONTAINER_BRANCH) no longer running (agent finished)."; \
				echo "[logs] Showing saved logs from $$LOG_FILE"; \
				echo "---"; \
				cat "$$LOG_FILE"; \
			else \
				echo "[logs] Container $(PROJECT_NAME)-$(CONTAINER_BRANCH) not found and no saved logs at $$LOG_FILE"; \
			fi; \
		}

follow-agent:
	@container logs -f $(PROJECT_NAME)-$(CONTAINER_BRANCH) 2>/dev/null \
		|| { \
			LOG_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/agent.log"; \
			if [ -f "$$LOG_FILE" ]; then \
				echo "[logs] Container $(PROJECT_NAME)-$(CONTAINER_BRANCH) no longer running (agent finished)."; \
				echo "[logs] Showing saved logs from $$LOG_FILE"; \
				echo "---"; \
				cat "$$LOG_FILE"; \
			else \
				echo "[logs] Container $(PROJECT_NAME)-$(CONTAINER_BRANCH) not found and no saved logs at $$LOG_FILE"; \
			fi; \
		}

status-agent:
	@STATUS_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/status.json"; \
	if [ -f "$$STATUS_FILE" ]; then \
		if command -v jq >/dev/null 2>&1; then \
			jq '.' "$$STATUS_FILE"; \
		else \
			cat "$$STATUS_FILE"; \
		fi; \
	else \
		echo "[status] No status file found for branch '$(BRANCH)'."; \
		echo "[status] Expected at: $$STATUS_FILE"; \
	fi

summary-agent:
	@container logs $(PROJECT_NAME)-$(CONTAINER_BRANCH) 2>/dev/null \
		| grep '^\[agent:' \
		|| { \
			LOG_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/agent.log"; \
			if [ -f "$$LOG_FILE" ]; then \
				grep '^\[agent:' "$$LOG_FILE" || echo "(no structured events found)"; \
			else \
				echo "(no logs available for branch '$(BRANCH)')"; \
			fi; \
		}

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

# ── PI Agent (local mlx_lm backend) ───────────────────────────────────────────
#
# PI agents are a separate class of agent that uses the pi.dev SDK with a
# LOCAL mlx_lm.server (hosted from /iac) as the OpenAI-compatible backend,
# instead of the Anthropic cloud API.
#
# Memory safety:
#   Gemma-4-26b + 6GB prompt cache leaves little RAM headroom on M-series.
#   MAX_PI_AGENTS=1 by default. Override only when you understand the cost.
#
# Open/Closed: this section adds new targets; no existing target is modified.
#
# Usage:
#   make build-pi
#   uv run iac server start       # in /iac, FIRST — start the local LLM
#   make spawn-pi  BRANCH=pi/refactor TASK="rename ambiguous helpers"
#   make list-pi-agents
#   make follow-pi-agent BRANCH=pi/refactor
#   make stop-pi-agent   BRANCH=pi/refactor

PI_IMAGE      ?= claude-pi:ubuntu
PI_DOCKERFILE ?= Dockerfile.pi
MAX_PI_AGENTS ?= 1
# Apple Container CLI does not implement host.containers.internal
# (apple/container#346). Containers reach the host via the bridge gateway IP,
# which matches the .1 address of the configured SUBNET (default
# 192.168.100.0/24 → gateway 192.168.100.1).
PI_BASE_URL   ?= http://192.168.100.1:8080/v1
PI_MODEL_ID   ?= mlx-community/gemma-4-26b-a4b-it-4bit

build-pi:
	container build --no-cache -f $(PI_DOCKERFILE) -t $(PI_IMAGE) .

spawn-pi: network
	@RUNNING=$$(container list 2>/dev/null | grep -c "$(PROJECT_NAME)-pi-" || true); \
	 if [ "$$RUNNING" -ge "$(MAX_PI_AGENTS)" ]; then \
	   echo "[error] MAX_PI_AGENTS=$(MAX_PI_AGENTS) reached ($$RUNNING PI agents running)."; \
	   echo "[error] Stop one with 'make stop-pi-agent BRANCH=<branch>' before spawning another."; \
	   echo "[error] Reason: the local model + cache leaves little RAM for concurrent agents."; \
	   exit 1; \
	 fi
	@mkdir -p "$(WORKTREES_DIR)"
	@echo "[pi-spawn] Launching PI agent: $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH)"
	@echo "[pi-spawn] Worktree: $(WORKTREES_DIR)/$(BRANCH)"
	@echo "[pi-spawn] Backend: $(PI_BASE_URL)"
	@echo "[pi-spawn] Task: $(TASK)"
	container run -d --rm \
		--name $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) \
		--network $(NETWORK) \
		--cpus $(CPUS) \
		--memory $(MEMORY) \
		--dns 1.1.1.1 \
		-v $(GIT_ROOT):/workspace \
		-v $(WORKTREES_DIR):/worktrees \
		-e PI_BASE_URL=$(PI_BASE_URL) \
		-e PI_MODEL_ID=$(PI_MODEL_ID) \
		$(PI_IMAGE) \
		--worktree "$(BRANCH)" --task "$(TASK)"
	@echo "[pi-spawn] Agent started. View logs: make follow-pi-agent BRANCH=$(BRANCH)"

list-pi-agents:
	@echo "[pi-agents] Active PI containers for project '$(PROJECT_NAME)':"
	@container list 2>/dev/null | grep "$(PROJECT_NAME)-pi-" || echo "  (none)"
	@echo ""
	@echo "[pi-agents] Worktrees in $(WORKTREES_DIR):"
	@if [ -d "$(WORKTREES_DIR)" ]; then \
		for dir in $(WORKTREES_DIR)/*/; do \
			[ -d "$$dir" ] || continue; \
			status_file="$$dir/.agent/status.json"; \
			if [ -f "$$status_file" ] && command -v jq >/dev/null 2>&1; then \
				kind=$$(jq -r '.agent_kind // ""' "$$status_file" 2>/dev/null || echo ""); \
				[ "$$kind" = "pi" ] || continue; \
				branch=$$(basename "$$dir"); \
				phase=$$(jq -r '.phase // "unknown"' "$$status_file" 2>/dev/null || echo "unknown"); \
				printf "  %-30s %s\n" "$$branch" "$$phase"; \
			fi; \
		done; \
	else \
		echo "  (none yet)"; \
	fi

logs-pi-agent:
	@[ -n "$(BRANCH)" ] || (echo "[error] BRANCH required"; exit 1)
	@container logs $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) 2>/dev/null \
		|| { \
			LOG_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/agent.log"; \
			if [ -f "$$LOG_FILE" ]; then \
				echo "[pi-logs] Container $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) no longer running (PI agent finished)."; \
				echo "[pi-logs] Showing saved logs from $$LOG_FILE"; \
				echo "---"; \
				cat "$$LOG_FILE"; \
			else \
				echo "[pi-logs] Container $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) not found and no saved logs at $$LOG_FILE"; \
			fi; \
		}

follow-pi-agent:
	@[ -n "$(BRANCH)" ] || (echo "[error] BRANCH required"; exit 1)
	@container logs -f $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) 2>/dev/null \
		|| { \
			LOG_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/agent.log"; \
			if [ -f "$$LOG_FILE" ]; then \
				echo "[pi-logs] Container $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) no longer running (PI agent finished)."; \
				echo "[pi-logs] Showing saved logs from $$LOG_FILE"; \
				echo "---"; \
				cat "$$LOG_FILE"; \
			else \
				echo "[pi-logs] Container $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) not found and no saved logs at $$LOG_FILE"; \
			fi; \
		}

status-pi-agent:
	@STATUS_FILE="$(WORKTREES_DIR)/$(BRANCH)/.agent/status.json"; \
	if [ -f "$$STATUS_FILE" ]; then \
		if command -v jq >/dev/null 2>&1; then \
			jq '.' "$$STATUS_FILE"; \
		else \
			cat "$$STATUS_FILE"; \
		fi; \
	else \
		echo "[pi-status] No status file found for branch '$(BRANCH)'."; \
		echo "[pi-status] Expected at: $$STATUS_FILE"; \
	fi

stop-pi-agent:
	@[ -n "$(BRANCH)" ] || (echo "[error] BRANCH required"; exit 1)
	@container stop $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) 2>/dev/null \
		&& echo "[pi-stop] PI agent $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) stopped." \
		|| echo "[pi-stop] PI agent $(PROJECT_NAME)-pi-$(CONTAINER_BRANCH) not found or already stopped."

clean-pi:
	container image delete $(PI_IMAGE) 2>/dev/null || true

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
	@echo "  PI agent targets (local mlx_lm backend):"
	@echo "    build-pi         Build $(PI_IMAGE) from $(PI_DOCKERFILE)"
	@echo "    spawn-pi         Spawn PI agent (MAX_PI_AGENTS=$(MAX_PI_AGENTS) guard)"
	@echo "    list-pi-agents   List active PI agents"
	@echo "    follow-pi-agent  Follow live logs of PI agent (BRANCH=...)"
	@echo "    status-pi-agent  Show status.json of PI agent (BRANCH=...)"
	@echo "    stop-pi-agent    Stop a PI agent (BRANCH=...)"
	@echo "    clean-pi         Remove the PI image"
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
