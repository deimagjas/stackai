# Evals — spawn-agent skill

## Qué son los evals

Los evals son casos de prueba automatizados para el skill `spawn-agent`. Miden si Claude, al tener el skill activo, produce las respuestas correctas (comandos, nombres de contenedores, prompts) ante distintos escenarios de uso.

Se comparan dos configuraciones:
- **with_skill**: Claude tiene acceso a las instrucciones del skill
- **without_skill**: Claude responde sin el skill (baseline)

El objetivo es cuantificar el valor que agrega el skill y detectar regresiones entre iteraciones.

---

## Escenarios de prueba

### Eval 1 — `spawn-feature`

**Prompt de prueba:**
> "I'm working on my stackai project and need you to spawn a virtual agent to implement OAuth2 authentication with JWT tokens in the API. Use branch feat/oauth2."

**Assertions (7):**
1. Genera `container run -d` (detached, no `-it`)
2. Usa `--worktree feat/oauth2` en el comando
3. Sanitiza la rama correctamente: `feat-oauth2` (un guión, no dos)
4. Monta worktrees con `-v $AGENTS_HOME:/worktrees` (no named volume)
5. Pasa `CLAUDE_CODE_OAUTH_TOKEN` como variable de entorno
6. El prompt del agente es tipo **feature** (menciona "senior software engineer")
7. Incluye comando para seguir logs (`container logs -f`)

### Eval 2 — `spawn-test`

**Prompt de prueba:**
> "Spawn an agent to write unit tests for the payment service module. Branch: test/payment-service"

**Assertions (5):**
1. Genera `container run -d` (detached)
2. Usa `--worktree test/payment-service`
3. Prompt tipo **test** (menciona QA engineer, coverage, edge cases)
4. No usa prompt de tipo feature ni mutation
5. Nombre de contenedor sanitizado: `test-payment-service` (un guión)

### Eval 3 — `list-agents`

**Prompt de prueba:**
> "Show me what agents are currently running. Also list the worktrees that exist."

**Assertions (4):**
1. Ejecuta `container list` (no `docker ps` ni `ps aux`)
2. Filtra por prefijo del proyecto (`grep PROJECT_NAME`)
3. Muestra worktrees en disco (`ls -la $AGENTS_HOME`)
4. No intenta lanzar un nuevo agente

### Eval 4 — `monitor-agent`

**Prompt de prueba:**
> "Check what the feat/oauth2 agent is doing right now. Give me a summary of its progress."

**Assertions (4):**
1. Usa `container logs` (no `container run` ni `container list`)
2. Nombre de contenedor correcto: incluye `feat-oauth2` (sanitización correcta)
3. Resume los logs en lenguaje natural (no dump raw)
4. No lanza un nuevo contenedor

---

## Estructura de archivos

```
~/.claude/skills/spawn-agent/
├── SKILL.md
└── evals/
    ├── evals.json              ← definición formal de los 4 evals
    ├── spawn_feature.md        ← descripción narrativa del escenario
    ├── spawn_test.md
    ├── list_and_monitor.md
    ├── stop_agent.md
    └── multi_agent.md

~/.claude/skills/spawn-agent-workspace/
├── iteration-1/               ← primera iteración del skill
│   ├── spawn-feature/
│   │   ├── with_skill/outputs/response.md
│   │   ├── with_skill/grading.json
│   │   ├── without_skill/outputs/response.md
│   │   └── without_skill/grading.json
│   ├── spawn-test/
│   ├── list-agents/
│   ├── monitor-agent/
│   └── benchmark.json
└── iteration-2/               ← skill mejorado (versión actual)
    ├── spawn-feature/
    ├── spawn-test/
    ├── list-agents/
    ├── monitor-agent/
    └── benchmark.json
```

---

## Resultados

### Iteración 1 — skill inicial

| Eval | with_skill | without_skill | Bug encontrado |
|---|---|---|---|
| spawn-feature | 85.7% | 0% | `feat--oauth2` doble guión |
| spawn-test | 80% | 20% | `test--payment-service` doble guión |
| list-agents | 25% | 50%* | Bash bloqueado en eval |
| monitor-agent | 50% | 50%* | Bash bloqueado en eval |
| **Media** | **60.7%** | **30%** | |

*El entorno de eval bloqueó Bash — los evals de list/monitor reflejan conocimiento del skill, no ejecución real.

**Bug crítico identificado:** `tr '/_ ' '---'` era ambiguo — los agentes interpretaban `'---'` como "triple guión" produciendo `feat--oauth2`. Debe ser `tr '/_ ' '-'`.

### Iteración 2 — skill corregido (actual)

| Eval | with_skill | without_skill | Delta |
|---|---|---|---|
| spawn-feature | **100%** | 0% | **+100%** |
| spawn-test | **100%** | 20% | **+80%** |
| list-agents | **100%** | 50% | **+50%** |
| monitor-agent | **100%** | 50% | **+50%** |
| **Media** | **100%** | **30%** | **+70%** |

**Cambios que corrigieron al 100%:**
1. `tr '/_ ' '-'` — reemplazo inequívoco, un guión siempre
2. `AGENTS_HOME` — variable de entorno reemplaza paths hardcodeados
3. `PROJECT_NAME=$(basename "$GIT_ROOT")` — nombre dinámico del proyecto
4. `container network list --format json` — parsing fiable de redes
5. Docs de Apple Container CLI incluidas en el skill

---

## Cómo ejecutar los evals

### Prerrequisitos

```bash
# Instalar el plugin skill-creator
/plugin skill-creator   # desde Claude Code
/reload-plugins
```

### Correr evals con skill-creator

```
/skill-creator:skill-creator run evals for the spawn-agent skill at ~/.claude/skills/spawn-agent/
```

El proceso:
1. Lee `evals/evals.json`
2. Lanza runs en paralelo (with_skill + without_skill)
3. Genera `benchmark.json` y abre el viewer HTML
4. Tú revisas outputs y dejas feedback
5. El skill se mejora y se repite

### Ejecutar directamente

```bash
SKILL_CREATOR=~/.claude/plugins/cache/claude-plugins-official/skill-creator/d5c15b861cd2/skills/skill-creator

# Generar viewer estático
python3.13 "$SKILL_CREATOR/eval-viewer/generate_review.py" \
  ~/.claude/skills/spawn-agent-workspace/iteration-2 \
  --skill-name "spawn-agent" \
  --benchmark ~/.claude/skills/spawn-agent-workspace/iteration-2/benchmark.json \
  --static /tmp/spawn-agent-review.html

open /tmp/spawn-agent-review.html
```

> **Python requerido:** Python 3.10+ (el sistema puede tener 3.9). Usar `~/.local/share/uv/python/cpython-3.13.0-macos-aarch64-none/bin/python3.13`

---

## Cómo añadir nuevos evals

### 1. Agregar a `evals.json`

```json
{
  "id": 5,
  "prompt": "Stop the feat/oauth2 agent and clean up its worktree",
  "expected_output": "Claude runs container stop stackai-feat-oauth2 and optionally removes the worktree",
  "files": [],
  "expectations": [
    "Runs container stop with correct container name stackai-feat-oauth2",
    "Does NOT attempt to spawn a new container",
    "If user asked for cleanup: runs git worktree remove and rm -rf"
  ]
}
```

### 2. Crear archivo de descripción (opcional)

```
~/.claude/skills/spawn-agent/evals/stop_agent.md
```

### 3. Correr la nueva iteración

```
/skill-creator:skill-creator run evals for spawn-agent, iterate from iteration-2
```

---

## Interpretación del benchmark.json

```json
{
  "run_summary": {
    "with_skill":    { "pass_rate": {"mean": 1.0, "stddev": 0.0} },
    "without_skill": { "pass_rate": {"mean": 0.3, "stddev": 0.2} },
    "delta":         { "pass_rate": "+0.70" }
  }
}
```

- **pass_rate mean > 0.8** con skill → skill funcionando bien
- **delta > 0.5** → skill aporta valor significativo
- **stddev alto** → eval posiblemente flaky o dependiente del entorno
- **with_skill ≈ without_skill** → assertion no discrimina (revisar)
