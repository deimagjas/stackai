#!/bin/bash
# Entrypoint for PI agent containers — local mlx_lm.server backend
#
# Interactive mode (default):
#   entrypoint-pi.sh                          → interactive bash
#   entrypoint-pi.sh <cmd> [args...]          → exec <cmd> [args...]
#
# Headless agent mode:
#   entrypoint-pi.sh --worktree <branch> --task "<prompt>"
#
# Expected volumes:
#   -v <git-root>:/workspace                  → main repository (read/write)
#   -v <parent>/.worktrees:/worktrees         → worktrees directory
#
# Expected env vars:
#   PI_BASE_URL       → OpenAI-compatible base URL of mlx_lm.server on host.
#                       Apple Container CLI does NOT implement
#                       host.containers.internal (apple/container#346), so
#                       the default is the bridge gateway IP: 192.168.100.1
#                       (gateway of the default 192.168.100.0/24 subnet).
#   PI_MODEL_ID       → model id served by mlx_lm.server (matches the
#                       --model flag passed when starting the server).
#   PI_PROVIDER_NAME  → provider key written into ~/.pi/agent/models.json
#                       (default: "local"). pi addresses the model as
#                       "<PI_PROVIDER_NAME>/<PI_MODEL_ID>".
#
# Unlike entrypoint.sh (Claude), this entrypoint does NOT copy any
# Claude credentials — PI agents authenticate against the local model
# via the OpenAI-compatible HTTP API, no cloud token needed.

set -euo pipefail

WORKTREE_BRANCH=""
AGENT_TASK=""
PASSTHROUGH_ARGS=()

# ── Functions ─────────────────────────────────────────────────────────────────

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --worktree) WORKTREE_BRANCH="$2"; shift 2 ;;
            --task)     AGENT_TASK="$2";      shift 2 ;;
            *)          PASSTHROUGH_ARGS+=("$1"); shift ;;
        esac
    done
}

create_worktree() {
    WORKTREE_PATH="/worktrees/${WORKTREE_BRANCH}"

    echo "[pi-entrypoint] Creating worktree: ${WORKTREE_BRANCH} → ${WORKTREE_PATH}"

    mkdir -p "$(dirname "$WORKTREE_PATH")"

    WORKTREE_BASE_SHA=$(git -C /workspace rev-parse HEAD 2>/dev/null || echo "")

    if git -C /workspace worktree add "$WORKTREE_PATH" -b "$WORKTREE_BRANCH" 2>/dev/null; then
        echo "[pi-entrypoint] Worktree created on new branch: ${WORKTREE_BRANCH}"
    elif git -C /workspace worktree add "$WORKTREE_PATH" "$WORKTREE_BRANCH" 2>/dev/null; then
        echo "[pi-entrypoint] Worktree created on existing branch: ${WORKTREE_BRANCH}"
    else
        echo "[pi-entrypoint] ERROR: could not create worktree for '${WORKTREE_BRANCH}'" >&2
        exit 1
    fi

    cd "$WORKTREE_PATH"
    echo "[pi-entrypoint] Working directory: $(pwd)"
}

setup_agent_perms() {
    echo "[pi-entrypoint] Preparing PI agent runtime..."
    chown -R agent:agent "$WORKTREE_PATH"
}

write_pi_models_config() {
    # Materialise ~/.pi/agent/models.json from env vars so the `pi` CLI knows
    # how to reach the local mlx_lm.server. Written to the agent user's home
    # since that is where `pi` looks for it.
    local pi_dir="/home/agent/.pi/agent"
    local base_url="${PI_BASE_URL:-http://192.168.100.1:8080/v1}"
    local model_id="${PI_MODEL_ID:-mlx-community/gemma-4-26b-a4b-it-4bit}"
    local provider="${PI_PROVIDER_NAME:-local}"

    mkdir -p "$pi_dir"
    cat > "$pi_dir/models.json" <<EOF
{
  "providers": {
    "${provider}": {
      "baseUrl": "${base_url}",
      "api": "openai-completions",
      "apiKey": "none",
      "compat": { "supportsDeveloperRole": false },
      "models": [
        { "id": "${model_id}" }
      ]
    }
  }
}
EOF
    chown -R agent:agent /home/agent/.pi
    echo "[pi-entrypoint] models.json → ${pi_dir}/models.json"
    echo "[pi-entrypoint] backend: ${base_url}"
    echo "[pi-entrypoint] model:   ${provider}/${model_id}"
}

write_status() {
    local phase="$1"; shift
    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    ( printf '{"phase":"%s","branch":"%s","task":"%s","started_at":"%s","agent_kind":"pi"}\n' \
        "$phase" "$WORKTREE_BRANCH" "$AGENT_TASK" "${AGENT_STARTED_AT:-${now}}" \
        > "${AGENT_DIR}/status.json" ) 2>/dev/null || true
}

emit_marker() {
    local phase="$1"; shift
    echo "[agent:status] PHASE=${phase} BRANCH=${WORKTREE_BRANCH} KIND=pi $*"
}

run_agent() {
    AGENT_DIR="${WORKTREE_PATH}/.agent"
    mkdir -p "$AGENT_DIR"
    chown -R agent:agent "$AGENT_DIR"

    if ! grep -qxF '.agent/' "${WORKTREE_PATH}/.gitignore" 2>/dev/null; then
        echo '.agent/' >> "${WORKTREE_PATH}/.gitignore" 2>/dev/null || true
    fi

    AGENT_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local start_epoch
    start_epoch=$(date +%s)

    write_status "starting"
    emit_marker "starting"

    write_status "working"
    emit_marker "working"

    local provider="${PI_PROVIDER_NAME:-local}"
    local model_id="${PI_MODEL_ID:-mlx-community/gemma-4-26b-a4b-it-4bit}"

    echo "[pi-entrypoint] Task: ${AGENT_TASK}"
    echo "---"

    set +e
    su-exec agent env HOME=/home/agent \
        pi -p "$AGENT_TASK" --model "${provider}/${model_id}" \
        2>&1 | tee "$AGENT_DIR/agent.log"
    local exit_code=${PIPESTATUS[0]}
    set -e

    local commit_count last_commit finished_at end_epoch duration_secs
    commit_count=$(git -C "$WORKTREE_PATH" -c "safe.directory=$WORKTREE_PATH" \
        rev-list --count "${WORKTREE_BASE_SHA:-HEAD}..HEAD" 2>/dev/null || echo 0)
    last_commit=$(git -C "$WORKTREE_PATH" -c "safe.directory=$WORKTREE_PATH" \
        log --oneline -1 2>/dev/null || echo "none")
    finished_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    end_epoch=$(date +%s)
    duration_secs=$((end_epoch - start_epoch))

    local final_phase="completed"
    [ "$exit_code" -ne 0 ] && final_phase="errored"

    ( printf '{
  "phase": "%s",
  "branch": "%s",
  "task": "%s",
  "agent_kind": "pi",
  "started_at": "%s",
  "finished_at": "%s",
  "duration_secs": %d,
  "exit_code": %d,
  "commits": %s,
  "last_commit": "%s"
}\n' "$final_phase" "$WORKTREE_BRANCH" "$AGENT_TASK" \
     "$AGENT_STARTED_AT" "$finished_at" "$duration_secs" \
     "$exit_code" "$commit_count" "$last_commit" \
     > "$AGENT_DIR/status.json" ) 2>/dev/null || true

    emit_marker "$final_phase" "EXIT_CODE=${exit_code}" "COMMITS=${commit_count}" "DURATION=${duration_secs}s"

    exit "$exit_code"
}

run_interactive() {
    if [[ ${#PASSTHROUGH_ARGS[@]} -eq 0 ]]; then
        exec /bin/bash --login
    else
        exec "${PASSTHROUGH_ARGS[@]}"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    parse_args "$@"

    if [[ -n "$WORKTREE_BRANCH" ]]; then
        create_worktree
        if [[ -n "$AGENT_TASK" ]]; then
            setup_agent_perms
            write_pi_models_config
            run_agent
        else
            write_pi_models_config
            run_interactive
        fi
    else
        write_pi_models_config
        run_interactive
    fi
}

main "$@"
