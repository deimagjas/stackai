"""PI agent lifecycle commands.

PI agents are an extension of the agent system that use the pi.dev SDK with
a LOCAL mlx_lm.server backend (managed via /iac) instead of the Anthropic
cloud API. They run in separate containers built from Dockerfile.pi.

Open/Closed: this module is a pure extension. The existing agents.py and
build.py are not modified — pi commands live under their own subapp.
"""

from __future__ import annotations

from typing import Annotated

import typer

from container_cli.targets import Target
from container_cli.utils import print_agent_status, run_make

app = typer.Typer(help="PI agent lifecycle (local mlx_lm.server backend)")


@app.command()
def build(
    image: Annotated[str | None, typer.Option("--image", help="PI image tag")] = None,
    dockerfile: Annotated[
        str | None, typer.Option("--dockerfile", help="Path to PI Dockerfile")
    ] = None,
) -> None:
    """Build the PI agent image (Ubuntu 26.04 + PI SDK)."""
    make_vars: dict[str, str] = {}
    if image:
        make_vars["PI_IMAGE"] = image
    if dockerfile:
        make_vars["PI_DOCKERFILE"] = dockerfile
    run_make(Target.BUILD_PI, make_vars)


@app.command()
def spawn(
    branch: Annotated[str, typer.Option("--branch", help="Git branch for the PI agent worktree")],
    task: Annotated[str, typer.Option("--task", help="Task description for the PI agent")],
    cpus: Annotated[int | None, typer.Option("--cpus", help="CPU count")] = None,
    memory: Annotated[str | None, typer.Option("--memory", help="Memory limit (e.g. 3G)")] = None,
    image: Annotated[str | None, typer.Option("--image", help="PI image tag")] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="Override the OpenAI-compatible base URL for the local LLM",
        ),
    ] = None,
    model_id: Annotated[
        str | None,
        typer.Option(
            "--model-id",
            help="Override the model id served by mlx_lm.server",
        ),
    ] = None,
) -> None:
    """Spawn a detached headless PI agent (local mlx_lm.server backend).

    The mlx_lm.server must be running on the host. Check with:
        uv run iac server status
    """
    typer.echo(
        "[pi] reminder: ensure mlx_lm.server is running (`uv run iac server status` from /iac)"
    )
    make_vars: dict[str, str] = {"BRANCH": branch, "TASK": task}
    if cpus is not None:
        make_vars["CPUS"] = str(cpus)
    if memory:
        make_vars["MEMORY"] = memory
    if image:
        make_vars["PI_IMAGE"] = image
    if base_url:
        make_vars["PI_BASE_URL"] = base_url
    if model_id:
        make_vars["PI_MODEL_ID"] = model_id
    run_make(Target.SPAWN_PI, make_vars)


@app.command(name="list")
def list_agents() -> None:
    """List active PI agent containers and PI worktrees."""
    run_make(Target.LIST_PI_AGENTS)


@app.command()
def logs(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Show logs for a PI agent (live container or persisted log)."""
    run_make(Target.LOGS_PI_AGENT, {"BRANCH": branch})


@app.command()
def follow(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Follow live streaming logs for a PI agent."""
    run_make(Target.FOLLOW_PI_AGENT, {"BRANCH": branch}, tty=True)


@app.command()
def stop(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Stop a PI agent container."""
    run_make(Target.STOP_PI_AGENT, {"BRANCH": branch})


@app.command()
def status(
    branch: Annotated[str, typer.Option("--branch", help="PI agent branch name")],
) -> None:
    """Show PI agent status from persisted status.json file."""
    print_agent_status(branch, label="pi-status")
