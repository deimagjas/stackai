#!/bin/bash
# Entrypoint — copia credenciales y soporta modo agente headless
#
# Modo interactivo (default):
#   entrypoint.sh                          → bash interactivo
#   entrypoint.sh <cmd> [args...]          → exec <cmd> [args...]
#
# Modo agente headless:
#   entrypoint.sh --worktree <branch> --task "<prompt>"
#   entrypoint.sh --worktree <branch> --task "<prompt>" --project <name>
#
# Volúmenes esperados:
#   -v <git-root>:/workspace               → repo principal (read/write)
#   -v <parent>/.worktrees:/worktrees      → directorio de worktrees
#   -v ~/.claude:/root/.claudenew:ro       → credenciales host
#   -v ~/.claude.json:/root/.claudenew.json:ro

set -euo pipefail

WORKTREE_BRANCH=""
AGENT_TASK=""
PROJECT_NAME=""
PASSTHROUGH_ARGS=()

# ── Parsear flags del modo agente ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --worktree) WORKTREE_BRANCH="$2"; shift 2 ;;
        --task)     AGENT_TASK="$2";      shift 2 ;;
        --project)  PROJECT_NAME="$2";    shift 2 ;;
        *)          PASSTHROUGH_ARGS+=("$1"); shift ;;
    esac
done

# ── Copiar credenciales desde mounts del host ──────────────────────────────────
echo "[entrypoint] Copiando credenciales..."
cp /root/.claudenew.json /root/.claude.json
mkdir -p /root/.claude
cp -r /root/.claudenew/. /root/.claude/
echo "[entrypoint] Credenciales listas."

# ── Modo agente: worktree + headless ──────────────────────────────────────────
if [[ -n "$WORKTREE_BRANCH" ]]; then
    WORKTREE_PATH="/worktrees/${WORKTREE_BRANCH}"

    echo "[entrypoint] Creando worktree: ${WORKTREE_BRANCH} → ${WORKTREE_PATH}"

    # Crear directorio de destino si no existe
    mkdir -p "$(dirname "$WORKTREE_PATH")"

    # Añadir worktree (idempotente: si ya existe la rama, simplemente la usa)
    if git -C /workspace worktree add "$WORKTREE_PATH" -b "$WORKTREE_BRANCH" 2>/dev/null; then
        echo "[entrypoint] Worktree creado en rama nueva: ${WORKTREE_BRANCH}"
    elif git -C /workspace worktree add "$WORKTREE_PATH" "$WORKTREE_BRANCH" 2>/dev/null; then
        echo "[entrypoint] Worktree creado sobre rama existente: ${WORKTREE_BRANCH}"
    else
        echo "[entrypoint] ERROR: no se pudo crear el worktree para '${WORKTREE_BRANCH}'" >&2
        exit 1
    fi

    cd "$WORKTREE_PATH"
    echo "[entrypoint] Directorio de trabajo: $(pwd)"

    if [[ -n "$AGENT_TASK" ]]; then
        echo "[entrypoint] Iniciando agente Claude (headless)..."
        echo "[entrypoint] Tarea: ${AGENT_TASK}"
        echo "---"
        # Make claude's install path traversable for non-root users (installed under /root/)
        # go+x required: agent is in group root (gid=0), so group bits apply, not others bits
        chmod go+x /root /root/.local /root/.local/share 2>/dev/null || true
        find /root/.local/share/claude -type d -exec chmod go+x {} + 2>/dev/null || true
        find /root/.local/share/claude/versions -maxdepth 1 -type f -exec chmod 755 {} + 2>/dev/null || true
        # Copy credentials to agent user's home (claude requires non-root for --dangerously-skip-permissions)
        cp -r /root/.claude/. /home/agent/.claude/ 2>/dev/null || true
        cp /root/.claude.json /home/agent/.claude.json 2>/dev/null || true
        chown -R agent:agent /home/agent/.claude /home/agent/.claude.json 2>/dev/null || true
        chown -R agent:agent "$WORKTREE_PATH"
        exec su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions -p "$AGENT_TASK"
    else
        # Worktree listo pero sin tarea: shell interactivo en el worktree
        exec /bin/bash --login
    fi
fi

# ── Modo interactivo (comportamiento original) ─────────────────────────────────
if [[ ${#PASSTHROUGH_ARGS[@]} -eq 0 ]]; then
    exec /bin/bash --login
else
    exec "${PASSTHROUGH_ARGS[@]}"
fi
