# Plan: Mutation CI + Acceptance Tests + CLAUDE.md TDD flow

## Contexto

El CI carece de enforcement en tests de mutación. No existe una capa que verifique
el comportamiento del CLI desde la perspectiva del usuario (Gherkin/BDD). Además,
se establece una nueva filosofía de desarrollo: los **acceptance tests son la fuente
de verdad** de la aplicación y el **flujo TDD** (acceptance → unit → implementación)
queda documentado en `CLAUDE.md`.

Este plan ha sido **revisado contra el estado real del código** antes de implementarse.
Las correcciones técnicas y decisiones cerradas están al final.

---

## Parte 1 — Tests de mutación en CI (umbral 70%)

**Objetivo**: fallar el pipeline si el kill rate cae por debajo del 70%.
Umbral conservador para permitir estabilidad semántica durante refactoring.
Score actual: 98.4% — pasará holgadamente.

### Implementación inline (sin script `.py` separado)

El check de threshold se implementa **directamente como target del Makefile**
con `python -c` para evitar crear `app/cli/scripts/`.

### Archivos

| Archivo | Cambio |
|---------|--------|
| `app/cli/Makefile` | Target `mutation-ci-threshold`: `mutmut export-cicd-stats \| python -c '<inline>'`, sale ≠ 0 si killed/total < 0.70 |
| `app/cli/pyproject.toml` | Comentar `# threshold = 70` en `[tool.mutmut]` (intención documentada) |
| `.github/workflows/ci.yml` | Job `mutation-tests` con `needs: [test-cli]`, artifact `mutants/` |

### Boceto del target

```makefile
mutation-ci-threshold: mutation-run
	@uv run mutmut export-cicd-stats | python -c '\
import json, sys; \
d = json.load(sys.stdin); \
killed, total = d["killed"], d["total"]; \
score = killed/total if total else 0; \
sys.exit(0 if score >= 0.70 else (print(f"FAIL: {score:.1%} < 70%") or 1))'
```

### CI job structure

```
mutation-tests:
  needs: [test-cli]
  steps: checkout → uv sync → make mutation-ci-threshold
  artifact: mutants/ (always, 14 días)
```

---

## Parte 2 — Acceptance tests (pytest-bdd, solo local)

**Objetivo**: verificar comportamiento del CLI desde la perspectiva del usuario,
expresado en Gherkin. Son **locales únicamente** — GitHub Actions no tiene Apple
Container CLI. Son el gate de calidad antes de PR.

### Acceptance tests como fuente de verdad

Los acceptance tests definen el comportamiento contratado de la aplicación.
No se modifican sin acuerdo explícito. Los unit tests y la implementación
deben estar al servicio de los acceptance tests, no al revés.

### Qué distingue acceptance de unit tests

Unit tests llaman funciones Python directamente con `mock_run_make`.
Acceptance tests invocan el CLI como usuario via `CliRunner.invoke(app, [...])`,
expresados en lenguaje de negocio. El mock de `run_make` se mantiene (sin
container real), pero el entry point es la interfaz pública del CLI.

### Estructura de directorios

```
app/cli/tests/
└── acceptance/
    ├── __init__.py
    ├── conftest.py           # fixture invocation_context: patches run_make en los 4
    │                         # módulos + find_git_root + AGENTS_HOME cleanup; expone
    │                         # mocks + CliRunner + tmp_path
    ├── features/
    │   ├── spawn.feature     # 3 escenarios: token válido, sin token, con recursos
    │   ├── agents.feature    # 4 escenarios: list, status ok, status missing, stop
    │   ├── build.feature     # 3 escenarios: defaults, imagen custom, clean-all
    │   └── network.feature   # 2 escenarios: defaults, subnet custom
    └── steps/
        ├── __init__.py
        ├── common_steps.py   # Given/When/Then compartidos
        ├── spawn_steps.py    # llama scenarios("../features/spawn.feature")
        ├── agents_steps.py   # llama scenarios("../features/agents.feature")
        ├── build_steps.py    # llama scenarios("../features/build.feature")
        └── network_steps.py  # llama scenarios("../features/network.feature")
```

### Decisiones técnicas clave (revisadas)

- **`CliRunner()` sin `mix_stderr`** — Click 8.3.1 removió ese flag; `result.output` ya
  mezcla stdout y stderr cuando se usa `typer.echo`.
- **`invocation_context` fixture** activa/desactiva patches vía yield; expone:
  - `runner` (`CliRunner()`)
  - `mocks` (dict de `run_make` mocks por módulo)
  - `git_root` (tmp_path como root patcheado en `find_git_root`)
  - `monkeypatch` (para gestionar env vars)
  - Limpia `AGENTS_HOME` al inicio (`monkeypatch.delenv("AGENTS_HOME", raising=False)`)
- **No mockear `check_token`** — el escenario "sin token" se valida por ausencia real
  de la env var `CLAUDE_CONTAINER_OAUTH_TOKEN`.
- **`agents status` no usa `run_make`** — lee `status.json` desde el filesystem.
  El escenario "status ok" debe **crear** físicamente
  `<git_root>/../.worktrees/<branch>/.agent/status.json` antes del `When`.
  El escenario "status missing" simplemente no crea el archivo y assertea `exit_code == 1`.
- **`"the make runner is ready"` step es no-op** — la fixture ya activó los mocks.
- **`clean/clean-all/clean-network` llaman `run_make("target")` sin segundo arg;
  `build`/`network` llaman `run_make("target", {})`** — distinción importante para asserts.

### Comandos no cubiertos (deuda técnica)

`agents logs`, `agents follow`, `agents summary` también usan `run_make` pero
quedan fuera de los 12 escenarios iniciales. Documentar para iteración futura.

### Cambios en archivos existentes

| Archivo | Cambio |
|---------|--------|
| `app/cli/pyproject.toml` | `pytest-bdd>=8` en dev deps; `testpaths = ["tests", "tests/acceptance"]` |
| `app/cli/Makefile` | Targets `acceptance-test`, `test-all`, `eval-skills`, `local-qa` |

### Eval target

Los evals del skill `spawn-agent` (scenarios LLM-graded en `evals.json`) se
invocan via Claude Code CLI. **Solo cubre `spawn-agent`** — cuando se añadan
más skills, se extenderá manualmente.

```makefile
eval-skills:
	claude -p "/skill-creator:skill-creator run evals for the spawn-agent skill at ~/.claude/skills/spawn-agent/"

local-qa: acceptance-test eval-skills
```

---

## Parte 3 — Actualización de CLAUDE.md

**Objetivo**: documentar la nueva filosofía de testing y el flujo TDD.

La sección "Skill evals" en CLAUDE.md (líneas 86-94) ya existe y se mantiene.
La nueva sección "Testing philosophy" se añade **separada** y referencia a
"Skill evals" sin duplicar contenido.

### Sección a agregar: "Testing philosophy"

#### Acceptance tests — fuente de verdad

Los acceptance tests (Gherkin en `tests/acceptance/features/`) definen el
comportamiento contratado de la aplicación. Son ejecutados localmente con
`make acceptance-test`. No se agregan al CI.

**Regla**: no modificar un acceptance test sin acuerdo explícito. Toda nueva
funcionalidad comienza con un acceptance test.

#### Flujo TDD (3 leyes)

Cuando se implementa una nueva feature o se corrige un bug:

1. **Escribe el acceptance test** en Gherkin que describa el comportamiento esperado
2. **Sigue las 3 leyes de TDD** para los unit tests:
   - Ley 1: No escribir código de producción sin tener un unit test que falle
   - Ley 2: No escribir más unit test del necesario para que falle (basta con que compile)
   - Ley 3: No escribir más código de producción del necesario para que el test pase
3. **Repite** el ciclo rojo → verde → refactor hasta que el acceptance test pase

Este flujo garantiza cobertura desde el contrato externo (acceptance) hasta la
implementación interna (unit), con tests de mutación como red de seguridad.

---

## Estrategia de implementación

**Las tres partes se implementan inline en esta conversación, secuencialmente.**
No se lanzan spawn-agents paralelos.

Razón: durante los acceptance tests (Parte 2) y los evals del skill `spawn-agent`
(Parte 3), el flujo lanzará contenedores Apple Container reales para validar el
comportamiento. Si además existiera un agente paralelo trabajando en
`feat/mutation-ci`, el host quedaría con 3+ contenedores activos simultáneos y
se podría agotar la memoria. Implementación serial → menor riesgo de OOM y
diagnóstico más limpio si algo falla.

### Orden

1. Parte 1 (Mutation CI) — bajo riesgo, aislado al Makefile/CI/pyproject.
2. Parte 2 (Acceptance tests) — el grueso del trabajo; verificar localmente con `make acceptance-test`.
3. Parte 3 (CLAUDE.md) — actualización documental, una vez que Parte 2 funciona.
4. Validación final con `make local-qa` (acceptance + eval-skills).

---

## Verificación (post-merge)

```bash
# Acceptance tests (local)
cd app/cli && make acceptance-test

# Mutation check (debe pasar: 98.4% > 70%)
make mutation-ci-threshold

# Todos los tests (unit + acceptance)
make test-all

# Skill evals
make eval-skills

# QA completo pre-PR
make local-qa
```

---

## Decisiones cerradas

| Decisión | Valor | Razón |
|----------|-------|-------|
| Threshold de mutación | **70%** | Holgura para refactor sin frenar CI |
| Cobertura `eval-skills` | **Solo `spawn-agent`** | Único skill con `evals.json` activo; extender manualmente |
| Ubicación del check de threshold | **Inline en Makefile** | Evita crear `app/cli/scripts/` |
| Estrategia de ejecución | **Serial inline**, sin spawn-agents paralelos | Evitar OOM al lanzar contenedores en Parte 2 + Parte 3 |
| `CliRunner` flag | **Sin `mix_stderr`** | Click 8.3.1 removió el flag; `result.output` ya mezcla |

---

## Funciones existentes a reutilizar

- `container_cli.utils.run_make` (`utils.py:32`) — entry point a Make.
- `container_cli.utils.find_git_root` (`utils.py:8`) — usado en `_agents_home()`.
- `container_cli.utils.check_token` (`utils.py`) — control real del flujo "sin token".
- `tests/conftest.py:17-28` — fixture `mock_run_make` (modelo a copiar).
- `tests/conftest.py:39-42` — fixture `env_with_token`.
- Targets `mutation-run`/`mutation-show`/`mutation-results` en `app/cli/Makefile`.

---

## Archivos afectados

| Acción | Archivo |
|--------|---------|
| Crear | `app/cli/tests/acceptance/conftest.py` |
| Crear | `app/cli/tests/acceptance/features/*.feature` (×4) |
| Crear | `app/cli/tests/acceptance/steps/*.py` (×5) |
| Crear | `app/cli/tests/acceptance/__init__.py`, `steps/__init__.py` |
| Modificar | `app/cli/pyproject.toml` |
| Modificar | `app/cli/Makefile` |
| Modificar | `.github/workflows/ci.yml` |
| Modificar | `CLAUDE.md` |
