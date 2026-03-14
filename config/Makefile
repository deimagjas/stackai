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
MEMORY     ?= 12G

# Host env var holding the OAuth token (avoids collision with host Claude instance)
HOST_TOKEN_VAR := CLAUDE_CONTAINER_OAUTH_TOKEN

.PHONY: build network run shell clean clean-network clean-all help

# ── Build ─────────────────────────────────────────────────────────────────────

build:
	container build --no-cache -f $(DOCKERFILE) -t $(IMAGE) .

# ── Network (macOS 26+) ───────────────────────────────────────────────────────

network:
	@container network list 2>/dev/null | grep -q "^$(NETWORK)" \
		&& echo "[network] $(NETWORK) already exists — skipping" \
		|| container network create --subnet $(SUBNET) $(NETWORK)

# ── Run ───────────────────────────────────────────────────────────────────────

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
		-v $(PWD):/workspace \
		--mount type=volume,source=stackai_worktrees_volume,target=/worktrees \
		-v $(HOME)/.claude:/root/.claudenew:ro \
		-v $(HOME)/.claude.json:/root/.claudenew.json:ro \
		-e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
		-e CLAUDE_CODE_OAUTH_TOKEN=$${$(HOST_TOKEN_VAR)} \
		$(IMAGE)

shell: run

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
	@echo "    build          Build image (no cache)"
	@echo "    network        Create bridge network $(NETWORK) ($(SUBNET))  [macOS 26+]"
	@echo "    run            Create network + run container interactively"
	@echo "    shell          Alias for run"
	@echo "    clean          Remove container + image $(IMAGE)"
	@echo "    clean-network  Remove network $(NETWORK)"
	@echo "    clean-all      Remove image + network"
	@echo ""
	@echo "  Variables (override with make <target> VAR=value):"
	@printf "    %-12s %s\n" "IMAGE"   "$(IMAGE)"
	@printf "    %-12s %s\n" "NAME"    "$(NAME)"
	@printf "    %-12s %s\n" "NETWORK" "$(NETWORK)"
	@printf "    %-12s %s\n" "SUBNET"  "$(SUBNET)"
	@printf "    %-12s %s\n" "CPUS"    "$(CPUS)"
	@printf "    %-12s %s\n" "MEMORY"  "$(MEMORY)"
	@echo ""
	@echo "  Required host env var:"
	@echo "    export $(HOST_TOKEN_VAR)=<your-oauth-token>"
	@echo ""
