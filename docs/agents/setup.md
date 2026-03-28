# Guía de Setup y Autenticación

## Por qué se requiere Claude Pro/Max

Los agentes virtuales ejecutan `claude -p` (modo headless) dentro de contenedores Apple Container. Este modo requiere un **token OAuth** que solo está disponible con una suscripción activa de **Claude Pro** o **Claude Max** en [claude.ai](https://claude.ai).

Sin una suscripción activa, el CLI no puede autenticar la sesión headless y el agente fallará inmediatamente con un error de autenticación.

---

## Cómo obtener tu token

### Paso 1 — Suscripción activa

Asegúrate de tener una suscripción **Pro** o **Max** activa en [claude.ai](https://claude.ai). Puedes verificar tu plan en **Settings → Subscription**.

### Paso 2 — Login desde Claude Code CLI

```bash
claude login
```

Este comando abre un flujo OAuth en tu navegador predeterminado. Autoriza el acceso cuando se te solicite.

### Paso 3 — Verificar el token almacenado

Una vez completado el flujo OAuth, el token se almacena automáticamente en `~/.claude/`. Puedes verificar que existe:

```bash
ls ~/.claude/
```

Deberías ver los archivos de credenciales generados por el CLI.

---

## Arquitectura de doble token

El sistema utiliza **dos variables de entorno distintas** para el token OAuth, una en el host y otra dentro del contenedor:

| Contexto | Variable | Propósito |
|---|---|---|
| Host | `CLAUDE_CONTAINER_OAUTH_TOKEN` | Token almacenado como variable de entorno en tu shell |
| Contenedor | `CLAUDE_CODE_OAUTH_TOKEN` | Token inyectado al contenedor, consumido por `claude -p` |

### Cómo se conectan

En el `Makefile`, la variable del host se define como:

```makefile
HOST_TOKEN_VAR := CLAUDE_CONTAINER_OAUTH_TOKEN
```

Y se mapea al contenedor mediante el flag `-e`:

```makefile
-e CLAUDE_CODE_OAUTH_TOKEN=$${$(HOST_TOKEN_VAR)}
```

Esto toma el valor de `CLAUDE_CONTAINER_OAUTH_TOKEN` en el host y lo inyecta como `CLAUDE_CODE_OAUTH_TOKEN` dentro del contenedor. El CLI de Claude lee esta variable automáticamente al iniciar.

### Por qué dos variables separadas

- **Aislamiento de sesión:** La sesión del contenedor es independiente de la sesión del host. Si un agente falla o su token expira, tu sesión local de Claude Code no se ve afectada.
- **Prevención de colisión de credenciales:** Evita que el contenedor sobrescriba o interfiera con los archivos de credenciales en `~/.claude/` del host.

---

## Configuración del entorno

Agrega las siguientes variables a tu `~/.zshrc` o `~/.bashrc`:

```bash
# Token OAuth para autenticación de agentes en contenedores
# ⚠️  Distinto del token de tu sesión host — evita colisiones
export CLAUDE_CONTAINER_OAUTH_TOKEN=<tu-oauth-token>

# Directorio donde se almacenarán los worktrees de los agentes
export AGENTS_HOME=~/agents
```

Aplica los cambios:

```bash
source ~/.zshrc   # o source ~/.bashrc
```

Verifica que las variables estén definidas:

```bash
echo $CLAUDE_CONTAINER_OAUTH_TOKEN
echo $AGENTS_HOME
```

---

## Cómo obtener `CLAUDE_CODE_OAUTH_TOKEN`

Ejecuta el siguiente comando en tu terminal:

```bash
claude setup-token
```

Esto genera el token OAuth y lo muestra en la salida. Cópialo y expórtalo:

```bash
export CLAUDE_CONTAINER_OAUTH_TOKEN=<token-obtenido>
```

Para hacerlo persistente, agrega la línea anterior a tu `~/.zshrc` o `~/.bashrc`.
