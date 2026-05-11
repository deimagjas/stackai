"""PI agent lifecycle commands.

PI agents are an extension of the agent system that use the pi.dev SDK with
a LOCAL mlx_lm.server backend (managed via /iac) instead of the Anthropic
cloud API. They run in separate containers built from Dockerfile.pi.

Open/Closed: this module is a pure extension. The existing agents.py and
build.py are not modified — pi commands live under their own subapp.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from container_cli.utils import find_git_root, run_make

app = typer.Typer(help="PI agent lifecycle (local mlx_lm.server backend)")


def _agents_home() -> Path:
    """Resolve AGENTS_HOME, falling back to sibling .worktrees/ directory."""
    env_val = os.environ.get("AGENTS_HOME")
    if env_val:
        return Path(env_val)
    return find_git_root().parent / ".worktrees"


@app.command()
def build(
    image: Annotated[
        str | None, typer.Option("--image", help="PI image tag")
    ] = None,
    dockerfile: Annotated[
        str | None, typer.Option("--dockerfile", help="Path to PI Dockerfile")
    ] = None,
) -> None:
    """Build the PI agent image (Ubuntu 26.04 + PI SDK)."""
    vars: dict[str, str] = {}
    if image:
        vars["PI_IMAGE"] = image
    if dockerfile:
        vars["PI_DOCKERFILE"] = dockerfile
    run_make("build-pi", vars)


@app.command()
def spawn(
    branch: Annotated[
        str, typer.Option("--branch", help="Git branch for the PI agent worktree")
    ],
    task: Annotated[
        str, typer.Option("--task", help="Task description for the PI agent")
    ],
    cpus: Annotated[int | None, typer.Option("--cpus", help="CPU count")] = None,
    memory: Annotated[
        str | None, typer.Option("--memory", help="Memory limit (e.g. 3G)")
    ] = None,
    image: Annotated[str | None, typer.Option("--image", help="PI image tag")] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="Override the OpenAI-compatible base URL for the local LLM",
        ),
    ] = None,
) -> None:
    """Spawn a detached headless PI agent (local mlx_lm.server backend).

    The mlx_lm.server must be running on the host. Check with:
        uv run iac server status
    """
    typer.echo(
        "[pi] reminder: ensure mlx_lm.server is running "
        "(`uv run iac server status` from /iac)"
    )
    vars: dict[str, str] = {"BRANCH": branch, "TASK": task}
    if cpus is not None:
        vars["CPUS"] = str(cpus)
    if memory:
        vars["MEMORY"] = memory
    if image:
        vars["PI_IMAGE"] = image
    if base_url:
        vars["PI_BASE_URL"] = base_url
    run_make("spawn-pi", vars)


@app.command(name="list")
def list_agents() -> None:
    """List active PI agent containers and PI worktrees."""
    run_make("list-pi-agents")


@app.command()
def logs(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Show logs for a PI agent (live container or persisted log)."""
    run_make("logs-pi-agent", {"BRANCH": branch})


@app.command()
def follow(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Follow live streaming logs for a PI agent."""
    run_make("follow-pi-agent", {"BRANCH": branch}, tty=True)


@app.command()
def stop(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Stop a PI agent container."""
    run_make("stop-pi-agent", {"BRANCH": branch})


@app.command()
def status(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Show PI agent status from persisted status.json file."""
    status_file = _agents_home() / branch / ".agent" / "status.json"
    if not status_file.exists():
        typer.echo(f"[pi-status] No status file found for branch '{branch}'.")
        typer.echo(f"[pi-status] Expected at: {status_file}")
        raise typer.Exit(1)
    data = json.loads(status_file.read_text())
    typer.echo(json.dumps(data, indent=2))
