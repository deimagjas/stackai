import json
import os
from pathlib import Path
from typing import Annotated

import typer

from container_cli.utils import check_token, find_git_root, run_make

app = typer.Typer(help="Agent lifecycle commands")


def _agents_home() -> Path:
    """Resolve AGENTS_HOME, falling back to sibling .worktrees/ directory."""
    env_val = os.environ.get("AGENTS_HOME")
    if env_val:
        return Path(env_val)
    return find_git_root().parent / ".worktrees"


@app.command()
def spawn(
    branch: Annotated[str, typer.Option("--branch", help="Git branch for the agent worktree")],
    task: Annotated[str, typer.Option("--task", help="Task description for the agent")],
    cpus: Annotated[int | None, typer.Option("--cpus", help="CPU count")] = None,
    memory: Annotated[str | None, typer.Option("--memory", help="Memory limit (e.g. 12G)")] = None,
    image: Annotated[str | None, typer.Option("--image", help="Image tag")] = None,
) -> None:
    """Spawn a detached headless agent container."""
    check_token()
    vars: dict[str, str] = {"BRANCH": branch, "TASK": task}
    if cpus is not None:
        vars["CPUS"] = str(cpus)
    if memory:
        vars["MEMORY"] = memory
    if image:
        vars["IMAGE"] = image
    run_make("spawn", vars)


@app.command(name="list")
def list_agents() -> None:
    """List active agent containers and worktrees."""
    run_make("list-agents")


@app.command()
def logs(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Show logs for a branch agent."""
    run_make("logs-agent", {"BRANCH": branch})


@app.command()
def follow(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Follow live streaming logs for a branch agent."""
    run_make("follow-agent", {"BRANCH": branch}, tty=True)


@app.command()
def stop(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Stop a branch agent container."""
    run_make("stop-agent", {"BRANCH": branch})


@app.command()
def status(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Show agent status from persisted status.json file."""
    status_file = _agents_home() / branch / ".agent" / "status.json"
    if not status_file.exists():
        typer.echo(f"[status] No status file found for branch '{branch}'.")
        typer.echo(f"[status] Expected at: {status_file}")
        raise typer.Exit(1)

    data = json.loads(status_file.read_text())
    typer.echo(json.dumps(data, indent=2))


@app.command()
def summary(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Show structured lifecycle events for a branch agent."""
    run_make("summary-agent", {"BRANCH": branch})
