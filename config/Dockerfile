# =============================================================================
# Claude Code — Multistage Alpine + Rust tools
# Optimizado para Apple Silicon (ARM64) / M4
#
# Stage 1 — builder : compila todas las herramientas Rust
# Stage 2 — runtime : solo los binarios + Node + Alpine base
# =============================================================================


# -----------------------------------------------------------------------------
# STAGE 1: builder
# Tiene Rust toolchain completo + musl-dev para compilar
# Esta imagen NO llega a producción
# -----------------------------------------------------------------------------
FROM alpine:3.21 AS builder

# Dependencias de compilación
RUN apk add --no-cache \
    curl \
    bash \
    musl-dev \
    gcc \
    make

# Rust toolchain minimal
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain stable --profile minimal

ENV PATH="/root/.cargo/bin:$PATH"

# Compilar todas las herramientas en un solo RUN
# para aprovechar cache de capas — si no cambia nada, no recompila
RUN cargo install \
    ripgrep \
    fd-find \
    bat \
    eza \
    du-dust \
    procs \
    bottom \
    && rm -rf /root/.cargo/registry /root/.cargo/git


# -----------------------------------------------------------------------------
# STAGE 2: runtime
# Imagen final — solo Alpine base + binarios copiados + Node
# Sin Rust, sin musl-dev, sin cargo — imagen mínima
# -----------------------------------------------------------------------------
FROM alpine:3.21 AS runtime

# -----------------------------------------------------------------------------
# Labels
# -----------------------------------------------------------------------------
LABEL maintainer="claude-code-agent"
LABEL description="Imagen ligera para agentes Claude Code con herramientas Rust"

# -----------------------------------------------------------------------------
# Variables de entorno
# -----------------------------------------------------------------------------
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TERM=xterm-256color
ENV PATH="/root/.local/bin:/usr/local/bin:$PATH"
ENV BAT_PAGER=""
ENV BAT_STYLE="numbers,changes,header"

# -----------------------------------------------------------------------------
# Dependencias runtime — solo lo necesario para ejecutar
# (sin musl-dev, gcc ni nada de compilación)
# -----------------------------------------------------------------------------
RUN apk add --no-cache \
    bash \
    curl \
    wget \
    git \
    git-lfs \
    openssh-client \
    ca-certificates \
    jq \
    unzip \
    tar \
    gzip \
    libgcc \
    tmux \
    nodejs \
    npm \
    python3 \
    py3-pip

# -----------------------------------------------------------------------------
# Copiar binarios compilados desde el stage builder
# -----------------------------------------------------------------------------
COPY --from=builder /root/.cargo/bin/rg        /usr/local/bin/rg
COPY --from=builder /root/.cargo/bin/fd        /usr/local/bin/fd
COPY --from=builder /root/.cargo/bin/bat       /usr/local/bin/bat
COPY --from=builder /root/.cargo/bin/eza       /usr/local/bin/eza
COPY --from=builder /root/.cargo/bin/dust      /usr/local/bin/dust
COPY --from=builder /root/.cargo/bin/procs     /usr/local/bin/procs
COPY --from=builder /root/.cargo/bin/btm       /usr/local/bin/btm

# -----------------------------------------------------------------------------
# Claude Code CLI — instalación nativa oficial
# Instala el lanzador en /root/.local/bin/claude (ya en PATH)
# Las credenciales y configuración llegan por volumen (-v ~/.claude:/root/.claude)
# No se necesita symlink: el script nativo instala directamente en ~/.local/bin
# -----------------------------------------------------------------------------
RUN curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh \
    && yes | bash /tmp/claude-install.sh \
    && rm -f /tmp/claude-install.sh

# -----------------------------------------------------------------------------
# OpenCode — binario precompilado desde GitHub releases
# El script oficial detecta arquitectura automáticamente (arm64 para M4)
# -----------------------------------------------------------------------------
RUN curl -fsSL https://opencode.ai/install | bash \
    && mv /root/.opencode/bin/opencode /usr/local/bin/opencode \
    && chmod 755 /usr/local/bin/opencode \
    && rm -rf /root/.opencode

# -----------------------------------------------------------------------------
# Aliases
# Definidos en /etc/profile.d/ para shells interactivas
# Para uso programático por Claude, complementar con system prompt
# -----------------------------------------------------------------------------
RUN cat > /etc/profile.d/rust-aliases.sh << 'EOF'
# Reemplazos Rust
alias grep='rg --smart-case --follow'
alias find='fd --follow'
alias cat='bat --paging=never'
alias ls='eza'
alias ll='eza -la --git'
alias la='eza -la'
alias lt='eza --tree --level=2'
alias du='dust'
alias ps='procs'
alias top='btm'
EOF

RUN echo 'source /etc/profile.d/rust-aliases.sh' >> /root/.bashrc \
    && echo 'source /etc/profile.d/rust-aliases.sh' >> /root/.profile

# -----------------------------------------------------------------------------
# Git config base
# -----------------------------------------------------------------------------
RUN git config --global init.defaultBranch main \
    && git config --global core.editor "true" \
    && git config --global advice.detachedHead false

# -----------------------------------------------------------------------------
# Directorio de trabajo — aquí se monta el volumen del repo
# -----------------------------------------------------------------------------
WORKDIR /workspace

SHELL ["/bin/bash", "--login", "-c"]
CMD ["/bin/bash", "--login"]
