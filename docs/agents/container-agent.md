# Imagen claude-agent:wolfi — Dockerfile y Makefile

## Visión general

`claude-agent:wolfi` es una imagen ARM64 (Apple Silicon M4) construida sobre Chainguard Wolfi. Está diseñada específicamente para correr instancias headless de Claude Code en contenedores Apple Container, con soporte para operación multi-agente en paralelo.

**Por qué Wolfi y no Alpine:**
Alpine usa la librería `musl`, y el binario de Claude ≥ 2.1.63 requiere `posix_getdents`, símbolo exclusivo de `glibc`. Wolfi es glibc-based con un footprint comparable a Alpine (~5 MB base), sin las incompatibilidades de musl.

---

## Dockerfile.wolfi — Explicación por etapas

### Stage 1: `builder` (compilación de herramientas Rust)

```dockerfile
FROM --platform=linux/arm64 cgr.dev/chainguard/rust:latest-dev AS builder
```

Compila en Rust las herramientas de productividad CLI:

| Herramienta | Propósito | Reemplaza |
|---|---|---|
| `rg` (ripgrep) | Búsqueda de texto ultra-rápida | `grep` |
| `fd` (fd-find) | Búsqueda de archivos | `find` |
| `bat` | Cat con syntax highlighting | `cat` |
| `eza` | Listado de archivos moderno | `ls` |
| `dust` | Visualización de uso de disco | `du` |
| `procs` | Listado de procesos moderno | `ps` |
| `btm` (bottom) | Monitor de sistema | `top` |

Los binarios compilados se copian al stage 2, manteniendo la imagen final limpia.

### Stage 2: `runtime` (imagen final)

```dockerfile
FROM --platform=linux/arm64 cgr.dev/chainguard/wolfi-base:latest AS runtime
```

**Paquetes del sistema instalados:**

```
bash, busybox, curl, wget        ← utilidades base
git, git-lfs                     ← control de versiones
openssh-client, ca-certificates  ← conectividad segura
jq, unzip, gzip                  ← procesamiento de datos
tmux                             ← multiplexor de terminal
gh                               ← GitHub CLI
nodejs-22, npm                   ← runtime JavaScript
python-3.13, py3-pip             ← runtime Python
```

**Herramientas adicionales instaladas:**

```
claude          ← Claude Code CLI (via install.sh oficial)
opencode        ← OpenCode AI CLI
openspec        ← @fission-ai/openspec (npm global)
```

**Variables de entorno configuradas:**

```dockerfile
LANG=C.UTF-8
LC_ALL=C.UTF-8
TERM=xterm-256color
PATH=/root/.local/bin:/usr/local/bin:$PATH
CLAUDE_CODE_DISABLE_AUTOUPDATE=1   ← evita auto-updates en contenedores
BAT_PAGER=""
BAT_STYLE="numbers,changes,header"
```

**Aliases Rust** (configurados en `/etc/profile.d/rust-aliases.sh`):

```bash
alias grep='rg --smart-case --follow'
alias find='fd --follow'
alias cat='bat --paging=never'
alias ls='eza'
alias ll='eza -la --git'
alias du='dust'
alias ps='procs'
alias top='btm'
```

**Configuración git global:**

```bash
git config --global init.defaultBranch main
git config --global core.editor "true"      # editor no-op (headless)
git config --global advice.detachedHead false
```

---

## entrypoint.sh — Modos de operación

El entrypoint soporta dos modos, seleccionados por los argumentos pasados al contenedor.

### Modo interactivo (default)

```bash
container run -it claude-agent:wolfi
# o
container run -it claude-agent:wolfi /bin/bash --login
```

**Flujo:**
1. Copia credenciales: `~/.claudenew.json` → `~/.claude.json` y `~/.claudenew/` → `~/.claude/`
2. Inicia shell bash interactiva con el perfil completo cargado

### Modo agente headless

```bash
container run -d --rm claude-agent:wolfi \
  --worktree "feat/oauth2" \
  --task "Implement OAuth2 with JWT tokens..."
```

**Argumentos del entrypoint:**

| Argumento | Descripción |
|---|---|
| `--worktree <branch>` | Nombre de la rama/worktree a crear |
| `--task "<prompt>"` | Prompt para Claude en modo headless |
| `--project <name>` | (opcional) Nombre del proyecto |

**Flujo:**
1. Copia credenciales desde mounts del host
2. `git -C /workspace worktree add /worktrees/<branch> -b <branch>`
   - Si la rama ya existe: `git worktree add /worktrees/<branch> <branch>`
3. `cd /worktrees/<branch>`
4. `claude --dangerously-skip-permissions -p "<task>"`

**Por qué `--dangerously-skip-permissions`:** En modo headless no hay usuario interactivo para aprobar permisos. El contenedor es un entorno sandboxed con acceso solo al worktree montado, por lo que es seguro saltarse las confirmaciones.

**Por qué correr como `agent` (non-root):** Claude CLI bloquea `--dangerously-skip-permissions` cuando el proceso corre como `root` (uid 0). El entrypoint usa `su-exec` para hacer drop al usuario `agent` antes de ejecutar Claude.

IMPORTANTE: **Por qué el worktree se crea dentro del contenedor:** Git necesita acceso al repositorio para registrar el worktree en `.git/worktrees/`. Como el repo está montado en `/workspace` dentro del contenedor, el worktree debe crearse desde allí. Si se creara desde el host directamente, el path registrado en git sería el path del host (`/Users/...`), que no existiría dentro del contenedor.

---

## Makefile — Referencia de targets

### Variables configurables

| Variable | Default | Descripción |
|---|---|---|
| `IMAGE` | `claude-agent:wolfi` | Nombre de la imagen Docker |
| `DOCKERFILE` | `Dockerfile.wolfi` | Dockerfile a usar |
| `NAME` | `qubits-team` | Nombre base para el contenedor interactivo |
| `NETWORK` | `claude-agent-net` | Red bridge de los agentes |
| `SUBNET` | `192.168.100.0/24` | CIDR de la red |
| `CPUS` | `8` | CPUs asignadas a cada contenedor |
| `MEMORY` | `12G` | RAM asignada a cada contenedor |
| `BRANCH` | `agent-<timestamp>` | Rama del agente a spawnear |
| `TASK` | `Explore the codebase...` | Tarea del agente |
| `AGENTS_HOME` | `<parent-de-git-root>/.worktrees` | Fallback si no está en env |

**Variables derivadas automáticamente:**

```makefile
GIT_ROOT      := $(shell git -C $(CURDIR) rev-parse --show-toplevel)
PROJECT_NAME  := $(shell basename $(GIT_ROOT))
AGENTS_HOME   ?= $(shell dirname $(GIT_ROOT))/.worktrees   # fallback
WORKTREES_DIR := $(AGENTS_HOME)
CONTAINER_BRANCH := $(shell echo "$(BRANCH)" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')
```

### Targets

#### `make build`
Construye la imagen sin caché.
```bash
make build
# equivale a: container build --no-cache -f Dockerfile.wolfi -t claude-agent:wolfi .
```

#### `make network`
Crea la red bridge `claude-agent-net` si no existe. Requiere macOS 26+.
```bash
make network
```

#### `make run` / `make shell`
Lanza el contenedor en modo interactivo (coordinador o sesión de desarrollo).
```bash
make run
make run NAME=mi-agente CPUS=4 MEMORY=8G
```
Requiere `CLAUDE_CONTAINER_OAUTH_TOKEN` exportado.

#### `make spawn`
Lanza un agente virtual en modo detached (headless). **El target principal para multi-agente.**
```bash
make spawn BRANCH=feat/oauth2 TASK="Implement OAuth2 with JWT"
make spawn BRANCH=test/auth TASK="Write unit tests for auth module"
make spawn BRANCH=mutation/payments TASK="Run mutation testing on payment service"
```
- Crea `$AGENTS_HOME` si no existe
- Lanza contenedor con nombre `${PROJECT_NAME}-${CONTAINER_BRANCH}`
- Muestra cómo ver los logs al terminar

#### `make list-agents`
Lista contenedores activos del proyecto y worktrees en disco.
```bash
make list-agents
```

#### `make logs-agent BRANCH=<rama>`
Muestra los logs del agente (snapshot).
```bash
make logs-agent BRANCH=feat/oauth2
```

#### `make follow-agent BRANCH=<rama>`
Sigue los logs del agente en tiempo real.
```bash
make follow-agent BRANCH=feat/oauth2
```

#### `make stop-agent BRANCH=<rama>`
Detiene el agente.
```bash
make stop-agent BRANCH=feat/oauth2
```

#### `make clean`
Elimina el contenedor y la imagen. No afecta los worktrees.
```bash
make clean
```

#### `make clean-network`
Elimina la red bridge.
```bash
make clean-network
```

#### `make clean-all`
Elimina imagen y red.
```bash
make clean-all
```

---

## Requisito de variable de entorno del host

```bash
# Obligatorio para usar make run, make spawn
export CLAUDE_CONTAINER_OAUTH_TOKEN=<tu-oauth-token>

# Recomendado (fallback si no está seteado: dirname(GIT_ROOT)/.worktrees)
export AGENTS_HOME=~/agents
```

**Por qué `CLAUDE_CONTAINER_OAUTH_TOKEN` y no `CLAUDE_CODE_OAUTH_TOKEN`:**
El Makefile mapea `CLAUDE_CONTAINER_OAUTH_TOKEN` del host a `CLAUDE_CODE_OAUTH_TOKEN` dentro del contenedor. Esto evita que el contenedor lea el token de la sesión host, manteniendo sesiones aisladas.

---

## Instrucciones de build

### Build estándar

```bash
cd /path/to/project/config
export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>
make build
```

El build puede tomar varios minutos la primera vez (compila 7 crates de Rust).

### Build rápido (reutilizar caché)

Editar el Makefile y cambiar `--no-cache`:
```makefile
build:
    container build -f $(DOCKERFILE) -t $(IMAGE) .   # sin --no-cache
```

### Verificar imagen

```bash
container image list | grep "claude-agent.*wolfi"
container run --rm claude-agent:wolfi claude --version
```

---

## Red bridge (macOS 26+)

La red `claude-agent-net` (CIDR `192.168.100.0/24`) permite que los contenedores se comuniquen entre sí y accedan a internet vía DNS `1.1.1.1` (Cloudflare).

```bash
# Crear
container network create --subnet 192.168.100.0/24 claude-agent-net

# Listar
container network list

# Inspeccionar
container network inspect claude-agent-net

# Eliminar
container network delete claude-agent-net
```

`make network` hace el create de forma idempotente (no falla si ya existe).

---

## Flujo de credenciales

```
Host                              Contenedor
────────────────────────────────────────────────────────
~/.claude/        ──(ro mount)──→ /root/.claudenew/
~/.claude.json    ──(ro mount)──→ /root/.claudenew.json
                                         │
                                  entrypoint.sh
                                  cp -r .claudenew/ → .claude/
                                  cp .claudenew.json → .claude.json
                                         │
                                  Claude Code usa /root/.claude/
                                  (lectura/escritura dentro del contenedor)

CLAUDE_CONTAINER_OAUTH_TOKEN  ──(env var)──→ CLAUDE_CODE_OAUTH_TOKEN
```

Los mounts son **read-only** desde el host para evitar que el contenedor modifique las credenciales originales. El entrypoint hace una copia local para que Claude pueda escribir en su directorio de configuración sin afectar el host.

---

## Usuario no-root para modo headless

Claude CLI bloquea `--dangerously-skip-permissions` cuando el proceso corre como `root` (uid 0). La imagen incluye un usuario `agent` (no-root) para el modo headless.

### Cambios en la imagen

```dockerfile
# su-exec: drop de privilegios con semántica exec (estándar Docker)
RUN apk add --no-cache su-exec

# Usuario agent (non-root)
RUN addgroup -S agent \
    && adduser -S -G agent -h /home/agent -s /bin/bash agent \
    && ln -sf /root/.local/bin/claude /usr/local/bin/claude
```

### Flujo de credenciales para modo headless

```
/root/.claude/         (copiado por entrypoint desde mount host)
       │
       └─► /home/agent/.claude/   (copiado + chown → agent)
                  │
           su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions -p "..."
```

El entrypoint:
1. Copia credenciales a `/root/.claude/` (como siempre)
2. Las copia también a `/home/agent/.claude/` con `chown agent`
3. Hace `chown agent` en el worktree
4. Ejecuta `su-exec agent` para hacer drop a uid no-root antes de llamar a Claude

### Por qué `su-exec` y no `su` o `runuser`

`su-exec` hace un `execvp` directo (reemplaza el proceso, no crea un subshell). Esto preserva las señales, el PID, y evita el overhead de un shell adicional. Es el estándar para entrypoints de contenedores Docker.

---

## Notas de seguridad

- Los contenedores corren con `--rm` (efímeros) — no persisten estado fuera del worktree
- Las credenciales se montan read-only desde el host
- `CLAUDE_CODE_DISABLE_AUTOUPDATE=1` evita que Claude descargue actualizaciones dentro del contenedor
- Cada contenedor tiene acceso solo al repo montado en `/workspace` y a `$AGENTS_HOME` en `/worktrees`
- `--dangerously-skip-permissions` es seguro en este contexto porque el filesystem accesible está limitado a los volúmenes montados
- El modo headless corre como usuario `agent` (non-root) por diseño
