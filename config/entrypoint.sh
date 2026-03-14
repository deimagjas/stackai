#!/bin/bash
# Entrypoint mínimo — solo copia credenciales desde los mounts del host

set -euo pipefail

# Los mounts vienen de:
#   -v ~/.claude:/root/.claudenew:ro
#   -v ~/.claude.json:/root/.claudenew.json:ro

echo "[entrypoint] Copiando credenciales..."

cp /root/.claudenew.json /root/.claude.json
mkdir -p /root/.claude
cp -r /root/.claudenew/. /root/.claude/

echo "[entrypoint] Listo."

if [ "$#" -eq 0 ]; then
    exec /bin/bash --login
else
    exec "$@"
fi
