"""
iac — local mlx_lm.server lifecycle manager.

Provides a small Typer CLI to start, stop, and check the status of the
local Gemma model served via `mlx_lm.server`. The server exposes an
OpenAI-compatible HTTP API on the configured port and is consumed by
PI agent containers running on the host.

Warning: the configured model + 6GB prompt cache leaves little RAM
headroom. Do not start more than one server instance, and limit the
number of concurrent PI agents that talk to it (MAX_PI_AGENTS=1).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="iac", help="Local mlx_lm.server lifecycle manager")
server_app = typer.Typer(help="mlx_lm.server lifecycle commands")
app.add_typer(server_app, name="server")

console = Console()


@dataclass(frozen=True)
class ServerConfig:
    """Defaults for the mlx_lm.server invocation. Overridable via env vars."""

    model: str = os.environ.get(
        "IAC_MODEL", "mlx-community/gemma-4-26b-a4b-it-4bit"
    )
    host: str = os.environ.get("IAC_HOST", "0.0.0.0")
    port: int = int(os.environ.get("IAC_PORT", "8080"))
    prompt_cache_size: int = 5
    prompt_cache_bytes: str = "6GB"
    decode_concurrency: int = 4
    prompt_concurrency: int = 2
    prefill_step_size: int = 1024
    temp: float = 0.9
    top_p: float = 0.95
    top_k: int = 40
    min_p: float = 0.0
    max_tokens: int = 2048
    log_level: str = "INFO"

    def command(self) -> list[str]:
        return [
            "mlx_lm.server",
            "--model", self.model,
            "--host", self.host,
            "--port", str(self.port),
            "--prompt-cache-size", str(self.prompt_cache_size),
            "--prompt-cache-bytes", self.prompt_cache_bytes,
            "--decode-concurrency", str(self.decode_concurrency),
            "--prompt-concurrency", str(self.prompt_concurrency),
            "--prefill-step-size", str(self.prefill_step_size),
            "--temp", str(self.temp),
            "--top-p", str(self.top_p),
            "--top-k", str(self.top_k),
            "--min-p", str(self.min_p),
            "--max-tokens", str(self.max_tokens),
            "--use-default-chat-template",
            "--log-level", self.log_level,
        ]


def _state_dir() -> Path:
    base = Path(os.environ.get("IAC_STATE_DIR", str(Path.home() / ".iac")))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _pid_file() -> Path:
    return _state_dir() / "server.pid"


def _log_file() -> Path:
    return _state_dir() / "server.log"


def _read_pid() -> int | None:
    pf = _pid_file()
    if not pf.exists():
        return None
    try:
        return int(pf.read_text().strip())
    except (ValueError, OSError):
        return None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return 200 <= resp.status < 500
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


@server_app.command("start")
def server_start(
    detach: bool = typer.Option(
        True,
        "--detach/--foreground",
        help="Run server in background (default) or foreground.",
    ),
) -> None:
    """Start mlx_lm.server with the project defaults."""
    existing_pid = _read_pid()
    if existing_pid and _process_alive(existing_pid):
        console.print(
            f"[yellow][server][/] already running (pid={existing_pid})"
        )
        raise typer.Exit(0)

    cfg = ServerConfig()
    cmd = cfg.command()

    console.print(f"[cyan][server][/] starting {cfg.model}")
    console.print(f"[cyan][server][/] listening on http://{cfg.host}:{cfg.port}")

    if detach:
        log = _log_file().open("ab")
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        _pid_file().write_text(str(proc.pid))
        console.print(f"[green][server][/] started (pid={proc.pid})")
        console.print(f"[server] logs: {_log_file()}")
    else:
        os.execvp(cmd[0], cmd)


@server_app.command("stop")
def server_stop() -> None:
    """Stop a running mlx_lm.server started via `iac server start`."""
    pid = _read_pid()
    if pid is None:
        console.print("[yellow][server][/] no pid file — not running")
        raise typer.Exit(0)

    if not _process_alive(pid):
        console.print(
            f"[yellow][server][/] pid {pid} not alive — clearing pid file"
        )
        _pid_file().unlink(missing_ok=True)
        raise typer.Exit(0)

    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _process_alive(pid):
            break
        time.sleep(0.25)
    else:
        os.kill(pid, signal.SIGKILL)

    _pid_file().unlink(missing_ok=True)
    console.print(f"[green][server][/] stopped (pid={pid})")


@server_app.command("status")
def server_status(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Report whether the server is running and reachable."""
    cfg = ServerConfig()
    pid = _read_pid()
    alive = pid is not None and _process_alive(pid)
    health_url = f"http://127.0.0.1:{cfg.port}/v1/models"
    reachable = _http_ok(health_url) if alive else False

    payload = {
        "phase": "running" if alive and reachable else "stopped",
        "pid": pid,
        "process_alive": alive,
        "endpoint_reachable": reachable,
        "model": cfg.model,
        "base_url": f"http://{cfg.host}:{cfg.port}/v1",
    }

    if as_json:
        console.print_json(json.dumps(payload))
        return

    table = Table(title="iac server status", show_header=False)
    table.add_column("field")
    table.add_column("value")
    for k, v in payload.items():
        table.add_row(k, str(v))
    console.print(table)


@app.command()
def info() -> None:
    """Print the resolved server config without starting anything."""
    cfg = ServerConfig()
    console.print_json(json.dumps({"command": cfg.command()}))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
