# spawn-agent — Coordinación de Agentes Virtuales

## Visión general

`spawn-agent` es un skill de Claude Code que convierte al host en un **coordinador de agentes virtuales**. Cada agente virtual es un contenedor Apple Container que corre Claude en modo headless (`claude -p`) dentro de un git worktree aislado, y reporta su progreso a través de `container logs`.

```
┌─────────────────────────────────────────────────────────────┐
│  Host (coordinador)                                          │
│  Claude Code + spawn-agent skill                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ stackai-     │  │ stackai-     │  │ stackai-     │       │
│  │ feat-oauth2  │  │ test-payment │  │ mutation-api │       │
│  │              │  │              │  │              │       │
│  │ claude -p    │  │ claude -p    │  │ claude -p    │       │
│  │ /worktrees/  │  │ /worktrees/  │  │ /worktrees/  │       │
│  │ feat/oauth2  │  │ test/payment │  │ mutation/api │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         ↑                  ↑                  ↑              │
│         └──────────────────┴──────────────────┘              │
│                  container logs (contexto)                    │
│                                                              │
│  $AGENTS_HOME/                                               │
│  ├── feat/oauth2/       ← worktree persiste post-container   │
│  ├── test/payment-service/                                   │
│  └── mutation/api/                                           │
└─────────────────────────────────────────────────────────────┘
```

### Por qué worktrees dentro del contenedor

Git worktrees deben crearse desde dentro de un contexto donde el repositorio sea accesible. El contenedor monta el repo principal en `/workspace` y los worktrees en `/worktrees`. El `entrypoint.sh` ejecuta `git -C /workspace worktree add /worktrees/<branch>` antes de lanzar Claude, garantizando aislamiento completo entre agentes.

---

## Prerrequisitos

### 1. Imagen Docker

```bash
cd /path/to/project/config
make build
```

Verifica que exista:
```bash
container image list | grep "claude-agent.*wolfi"
```

### 2. Variables de entorno (una vez en `~/.zshrc` o `~/.bashrc`)

```bash
# Directorio donde se almacenarán los worktrees de los agentes
export AGENTS_HOME=~/agents          # o cualquier ruta persistente

# Token OAuth para que Claude autentique dentro del contenedor
# ⚠️  Distinto del token de tu sesión host — evita colisiones
export CLAUDE_CONTAINER_OAUTH_TOKEN=<tu-oauth-token>
```

> **Por qué dos tokens?** Claude Code usa `~/.claude/` del host para la sesión interactiva. Los contenedores reciben el token vía variable de entorno, evitando que dos instancias de Claude compitan por el mismo estado de sesión.

---

## Flujo principal

```
1. Usuario le pide a Claude una tarea → skill se activa automáticamente
         │
         ▼
2. Claude verifica AGENTS_HOME y CLAUDE_CONTAINER_OAUTH_TOKEN
         │ (si faltan → muestra qué exportar)
         ▼
3. Claude determina el tipo de agente (feature / test / mutation / explore)
   y construye el prompt adecuado
         │
         ▼
4. Claude calcula variables de ruta:
   GIT_ROOT       = git rev-parse --show-toplevel
   PROJECT_NAME   = basename $GIT_ROOT
   CONTAINER_NAME = ${PROJECT_NAME}-$(echo $BRANCH | tr '/_ ' '-' | tr A-Z a-z)
         │
         ▼
5. container run -d --rm  ← detached (no bloquea)
   • -v $GIT_ROOT:/workspace          ← repo completo (read/write)
   • -v $AGENTS_HOME:/worktrees       ← destino de worktrees
   • --worktree $BRANCH               → entrypoint crea el worktree
   • --task "$TASK"                   → claude -p "$TASK" en el worktree
         │
         ▼
6. Dentro del contenedor (entrypoint.sh):
   a) Copia credenciales desde mounts host → /root/.claude/
   b) git -C /workspace worktree add /worktrees/$BRANCH -b $BRANCH
   c) cd /worktrees/$BRANCH
   d) claude --dangerously-skip-permissions -p "$TASK"
         │
         ▼
7. Claude en el agente trabaja autónomamente:
   lee codebase → implementa → commitea → sale
         │
         ▼
8. Coordinador puede leer progreso en tiempo real:
   container logs -f ${CONTAINER_NAME}
         │
         ▼
9. Al terminar: contenedor se elimina (--rm), worktree persiste en AGENTS_HOME
```

---

## Tipos de agente y prompts automáticos

El skill construye el prompt según el tipo detectado de la petición del usuario:

### `feature` — nueva funcionalidad

**Cuándo**: el usuario pide implementar algo nuevo.

```
You are a senior software engineer. Implement the following in this codebase:
<descripción del usuario>
Requirements:
- Write clean, tested, production-ready code
- Follow existing conventions (read the codebase first)
- Create a git commit when done with a descriptive message
```

### `test` — pruebas unitarias

**Cuándo**: el usuario pide escribir o mejorar tests.

```
You are a senior QA engineer. Your task:
<descripción del usuario>
Requirements:
- Identify untested or poorly tested code
- Write comprehensive unit tests
- Aim for high coverage of edge cases
- Run the tests and verify they pass
- Commit the tests when done
```

### `mutation` — mutation testing

**Cuándo**: el usuario pide mutation testing o análisis de cobertura de tests.

```
You are a mutation testing expert. Your task:
<descripción del usuario>
Requirements:
- Analyze existing tests for weak assertions
- Introduce mutations and verify tests catch them
- Strengthen tests that miss mutations
- Report a summary of findings
- Commit improvements when done
```

### `explore` / general

**Cuándo**: cualquier otra tarea de código.

```
You are a senior software engineer. Your task:
<descripción del usuario>
Work autonomously, read the codebase as needed, and commit any changes.
```

---

## Nomenclatura de contenedores

El nombre del contenedor se deriva automáticamente del proyecto y la rama:

```
CONTAINER_NAME = <PROJECT_NAME>-<CONTAINER_BRANCH>

donde:
  PROJECT_NAME   = basename $(git rev-parse --show-toplevel)
  CONTAINER_BRANCH = echo $BRANCH | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]'
```

| Branch | PROJECT_NAME | CONTAINER_NAME |
|---|---|---|
| `feat/oauth2` | `stackai` | `stackai-feat-oauth2` |
| `test/payment-service` | `stackai` | `stackai-test-payment-service` |
| `mutation/API_v2` | `stackai` | `stackai-mutation-api-v2` |

> **Regla de sanitización**: cada `/`, `_` o espacio se convierte en un único `-`, y se pasa a minúsculas. Se usa `tr '/_ ' '-'` (no `'---'`) para garantizar reemplazo 1:1.

---

## Ejemplo completo — feature agent

### Escenario
Queremos implementar OAuth2 con JWT en la API, en rama `feat/oauth2`, sin tocar el branch `main`.

### 1. Invocar al coordinador

```
"Spawn an agent to implement OAuth2 authentication with JWT tokens. Branch: feat/oauth2"
```

El skill se activa automáticamente.

### 2. Lo que Claude ejecuta

```bash
# Verificación de vars
test -n "$CLAUDE_CONTAINER_OAUTH_TOKEN" || echo "ERROR: export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>"
test -n "$AGENTS_HOME"                  || echo "ERROR: export AGENTS_HOME=<path>"

# Variables
GIT_ROOT=$(git rev-parse --show-toplevel)     # /home/user/projects/stackai
PROJECT_NAME=$(basename "$GIT_ROOT")           # stackai
BRANCH="feat/oauth2"
CONTAINER_BRANCH=$(echo "$BRANCH" | tr '/_ ' '-' | tr '[:upper:]' '[:lower:]')
# => feat-oauth2
CONTAINER_NAME="${PROJECT_NAME}-${CONTAINER_BRANCH}"
# => stackai-feat-oauth2

# Red (macOS 26+)
container network list --format json 2>/dev/null | grep -q '"claude-agent-net"' \
  || container network create --subnet 192.168.100.0/24 claude-agent-net

# Directorio de worktrees
mkdir -p "${AGENTS_HOME}"

# Lanzar agente
TASK="You are a senior software engineer. Implement the following in this codebase:
Implement OAuth2 authentication with JWT tokens in the API.
Requirements:
- Write clean, tested, production-ready code
- Follow existing conventions (read the codebase first)
- Create a git commit when done with a descriptive message"

container run -d --rm \
  --name "stackai-feat-oauth2" \
  --network claude-agent-net \
  --cpus 8 --memory 12G --dns 1.1.1.1 \
  -v "${GIT_ROOT}:/workspace" \
  -v "${AGENTS_HOME}:/worktrees" \
  -v "${HOME}/.claude:/root/.claudenew:ro" \
  -v "${HOME}/.claude.json:/root/.claudenew.json:ro" \
  -e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
  -e "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CONTAINER_OAUTH_TOKEN}" \
  claude-agent:wolfi \
  --worktree "feat/oauth2" --task "${TASK}"

# Confirmar
container list | grep "stackai-feat-oauth2"
```

### 3. Monitorear progreso

```bash
# Últimas 100 líneas (snapshot)
container logs -n 100 stackai-feat-oauth2

# En tiempo real
container logs -f stackai-feat-oauth2
```

Claude resume los logs y te explica en qué paso está el agente.

### 4. Resultado

Al terminar, el agente habrá:
- Creado la rama `feat/oauth2`
- Implementado OAuth2 + JWT en la rama
- Hecho commit con mensaje descriptivo
- Salido (contenedor eliminado automáticamente)

El worktree persiste en `$AGENTS_HOME/feat/oauth2/` para que puedas revisar el código.

### 5. Revisar y mergear

```bash
# Ver los commits del agente
git -C "$AGENTS_HOME/feat/oauth2" log --oneline -10

# Diff contra main
git -C "$GIT_ROOT" diff main..feat/oauth2 --stat

# Mergear si estás satisfecho
git -C "$GIT_ROOT" merge feat/oauth2

# Limpiar worktree
git -C "$GIT_ROOT" worktree remove --force "$AGENTS_HOME/feat/oauth2"
rm -rf "$AGENTS_HOME/feat/oauth2"
```

---

## Referencia de operaciones

### Listar agentes activos

```
"Show me what agents are currently running"
```

Claude ejecuta:
```bash
container list | grep "${PROJECT_NAME}"
ls -la "${AGENTS_HOME}"
```

### Monitorear un agente específico

```
"What is the feat/oauth2 agent doing?"
```

Claude ejecuta `container logs -n 100 stackai-feat-oauth2` y te da un resumen en lenguaje natural.

### Detener un agente

```
"Stop the feat/oauth2 agent"
```

Claude ejecuta:
```bash
container stop stackai-feat-oauth2
```

Opcionalmente limpia el worktree si lo pides.

### Lanzar múltiples agentes en paralelo

```
"Spawn three agents: one for OAuth, one for tests on auth, one for mutation testing on payments"
```

Claude lanza los tres contenedores en secuencia (detached), cada uno con su propia rama y prompt.

---

## Referencia Apple Container CLI

```
container run -d --rm --name <n> --network <net> --cpus <n> --memory <n>G
             --dns <ip> -v <host>:<container> -e KEY=VAL <image> [args...]

container list [--all] [--format json|table] [-q]
container logs [-f] [-n <lines>] <container-id>
container stop [--signal <sig>] [--time <sec>] <container-id>
container network list [--format json|table]
container network create --subnet <cidr> <name>
```

Docs completos: https://github.com/apple/container/blob/main/docs/command-reference.md

---

## Solución de problemas

| Problema | Causa | Solución |
|---|---|---|
| `ERROR: export AGENTS_HOME` | Variable no seteada | `export AGENTS_HOME=~/agents` en `~/.zshrc` |
| `ERROR: export CLAUDE_CONTAINER_OAUTH_TOKEN` | Token no seteado | `export CLAUDE_CONTAINER_OAUTH_TOKEN=<token>` |
| `Image not found: claude-agent:wolfi` | Imagen no construida | `cd config && make build` |
| Worktree creation failed | Rama ya existe en el repo | El entrypoint intenta `worktree add` con rama existente — funciona |
| Container exits immediately | Error en entrypoint | `container logs <name>` para ver el error |
| Nombre de contenedor duplicado | Agente ya corriendo | `container list` para verificar; `container stop <name>` para liberarlo |
