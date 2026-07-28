# Auditoría YAGNI + seguridad — 2026-06-12

Auditoría multi-agente (workflow de 20 agentes: 4 finders en paralelo + verificación
adversarial de cada hallazgo). Resultado: 16 hallazgos brutos → **14 confirmados, 2 refutados**.
Todo lo aplicado quedó verificado con la suite completa.

## Verificación final

| Gate | Resultado |
|---|---|
| `uv run pytest` (unit + acceptance) | 135 passed (100 previos + 35 nuevos de validación) |
| `uv run ruff check .` | limpio |
| `make mutation-ci-threshold` | 95.2% (178/187), umbral 70% |
| `shellspec --shell bash` (entrypoint) | 59 examples, 0 failures |

## Código muerto eliminado (YAGNI)

| Qué | Dónde | Evidencia |
|---|---|---|
| Dependencia directa `rich>=13` | `app/cli/pyproject.toml` | Ningún módulo de `container_cli/` ni sus tests importa `rich`; Typer ya lo trae transitivamente (sigue en `uv.lock` como dep de typer). Docs actualizadas: `CLAUDE.md` («Typer+Rich» → «Typer») y `docs/agents/cli.md`. |
| `from __future__ import annotations` | `commands/pi_agents.py:11` | `requires-python >= 3.13`; toda anotación usada (`str \| None`) es nativa. Los 4 módulos hermanos no lo usan. |
| Alias `agents_app = agents.app` | `main.py:8` | Indirección de un solo uso; ahora se registra directo `app.add_typer(agents.app, ...)`, igual que `pi_agents.app`. |
| `plans/testing-ci-acceptance-tdd.md` | `plans/` (carpeta completa) | Plan ya implementado (gate de mutación y filosofía TDD viven en CLAUDE.md); cero referencias en README, docs, Makefile o CI. |
| `.claude/skills/spawn-agent-workspace/iteration-1/` | (no versionado) | Artefacto de evals superado por `iteration-2/`. Se conservan `iteration-2/` y `skill-snapshot/` — son la línea base de regresión más reciente (única corrida con los evals PI 9–11). |
| `.DS_Store` y `__pycache__` sueltos | repo completo | Limpieza local; ninguno estaba trackeado, `.gitignore` ya los cubre. |

## Documentación desactualizada corregida

- **`CLAUDE.md`**: `spawn-agent-workspace` aparecía listado como skill; es el workspace
  (gitignorado) de salida de evals. Redactado corregido.
- **`.claude/skills/spawn-agent/evals/`** (5 archivos): prefijo de contenedor hardcodeado
  `qubits-team` (nombre antiguo del proyecto) → regla derivada `<project-name>` (basename
  del git root, p. ej. `stackai`). Afectaba `evals.json`, `spawn_feature.md`,
  `list_and_monitor.md`, `stop_agent.md`, `multi_agent.md`.
  ⚠️ **Pendiente**: re-ejecutar los evals del skill (`/skill-creator:skill-creator run evals…`)
  según CLAUDE.md — el runner de evals no está disponible en esta sesión.

## Código inseguro corregido

### 1. Validación de entrada en el CLI (`--branch` / `--task`) — severidad ALTA
`q spawn --branch 'foo; rm -rf x'` llegaba sin sanitizar a la recipe del Makefile, donde
el shell del host la expande (inyección de comandos); un branch `../../x` permitía
path traversal en `print_agent_status` (`utils.py`).

Fix (TDD: Gherkin → unit → implementación):
- `utils.validate_branch()`: solo `[A-Za-z0-9._/-]`, debe empezar por alfanumérico
  (bloquea `-flag` y `/abs`), rechaza `..` y vacío. Cableado en los 11 comandos que
  reciben `--branch` (agents: spawn/logs/follow/stop/status/summary; pi: spawn/logs/follow/stop/status).
- `utils.validate_task()`: rechaza vacío y caracteres de control (`\n`, `\r`, `\t`, NUL, DEL).
- `print_agent_status()`: guard de contención — el path resuelto debe quedar dentro de
  `$AGENTS_HOME` (defensa en profundidad contra traversal).
- Tests nuevos: `tests/acceptance/features/input_validation.feature` (6 escenarios) +
  `TestValidateBranch`/`TestValidateTask`/2 tests de traversal en `test_utils.py`.

### 2. Inyección JSON en `status.json` — `config/entrypoint.sh`
`$AGENT_TASK` y `$last_commit` se interpolaban sin escapar en el `printf` del JSON
(líneas 97 y 159): una tarea o mensaje de commit con `"` producía JSON inválido y
rompía `q agents status` (`json.loads`). Añadida `json_escape()` (escapa `\`, `"`,
`\t`, `\r`, `\n`) aplicada a branch, task y last_commit. Shellspec verde.

### 3. Skill `spawn-agent` — regla de asignación segura (SKILL.md)
Riesgo verificado: si el agente que sigue el skill escribe el texto del usuario
**literalmente** dentro de comillas dobles (`--task "...$(...)..."`), el host expande
`$(...)`/backticks antes de llegar al contenedor. Añadido «Step 0» al flujo de spawn:
asignar `TASK` vía heredoc con delimitador entre comillas simples (`<<'EOF'`, sin
expansión) y la misma regla de charset de branch que aplica el CLI.

## Hallazgos REFUTADOS por la verificación adversarial (sin cambios)

- **«`chmod go+x /root` expone credenciales al usuario agent»** — falso: `x` solo da
  traversal, no lectura; `cp` sin `-p` hereda el modo del origen enmascarado por umask
  (verificado empíricamente: fuente 600 → copia 600), y `~/.claude.json` del host es 600.
- **«Credenciales copiadas con permisos world-readable por umask»** — falso por la misma
  semántica de `cp`: umask solo puede quitar bits, nunca añadirlos.

## Decisiones diferidas (requieren al dueño del repo / cambio coordinado)

2. **Fix de fondo del sink TASK en `config/Makefile:132,284`** (`--task "$(TASK)"` se
   re-interpola en la recipe). La validación del CLI mitiga el vector, pero el sink sigue:
   la corrección correcta es pasar TASK por env var o archivo en vez de argv de make, y
   exige tocar `entrypoint.sh` (parsea `--task` de argv) + re-ejecutar `make e2e-test`
   con contenedores reales. No aplicado en caliente a propósito.
3. **Token visible en argv de `container run`** (`-e CLAUDE_CODE_OAUTH_TOKEN=…`,
   `config/Makefile:100,130`) — visible en `ps` del host mientras el contenedor vive.
   Diseño de fix ya elaborado (`--env-file` + archivo temporal `mktemp`/`trap`, confirmado
   que Apple Container CLI soporta `--env-file`) pero **explícitamente pausado a pedido
   del usuario el 2026-07-27** — se mantiene el mecanismo actual sin cambios por ahora.

## Seguimiento — 2026-07-27

Resolución de los puntos diferidos 1 y 4, más ejecución de los e2e:

1. **Submódulos eliminados.** `git submodule deinit -f` + `git rm -f` + limpieza de
   `.git/modules/` para `model/gemma3-finetunning` y `app/agents-templates`; `.gitmodules`
   quedó vacío y se eliminó. `README.md` (diagrama de árbol) actualizado. Verificado:
   `git submodule status` vacío, sin referencias residuales en código/docs/CI.
2. **Tests e2e ejecutados** (`app/cli/tests/e2e/`, ambos con contenedores reales):
   - `test_pi_agent_e2e.py` — confirmado que lanza el modelo local (`mlx_lm.server`).
     Antes de correrlo se reconstruyó `claude-pi:ubuntu` (`make build-pi`); la imagen no
     fija versión del paquete `@earendil-works/pi-coding-agent` y el build usa
     `--no-cache`, así que el rebuild ya trae la última versión de npm sin tocar el
     Dockerfile.
   - `test_claude_agent_e2e.py` — corrido también a pedido del usuario, gasta créditos
     reales de la API de Anthropic.
   - Resultado: **2 passed** en ~3.5 min. Sin contenedores huérfanos tras la limpieza
     automática de los tests.
4. **Evals del skill `spawn-agent` re-ejecutados** (iteration-3, vía el flujo del plugin
   skill-creator) para validar los cambios de la sesión anterior (Step 0 de asignación
   segura de TASK/BRANCH, genericización del prefijo de proyecto en `evals/`). Nota
   importante: existe una copia **global** del skill en `~/.claude/skills/spawn-agent/`
   que diverge de la copia del repo (le falta el Step 0 y el bloque `AGENT_MODEL`) — hay
   que apuntar explícitamente a la ruta del repo al re-ejecutar evals, no a la ruta
   genérica de `CLAUDE.md`. Resultado: **11/11 evals, 100% pass rate en ambas
   configuraciones (with_skill vs. baseline pre-edición), delta +0.00** — sin regresión.
   El nuevo Step 0 se ve aplicado correctamente en las respuestas (heredoc single-quoted
   para TASK). Benchmark en
   `.claude/skills/spawn-agent-workspace/iteration-3/benchmark.json` (gitignorado).
