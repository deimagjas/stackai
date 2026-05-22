"""Interactive coordinator container (`run` and `shell` aliases)."""

from typing import Annotated

import typer

from container_cli.targets import Target
from container_cli.utils import check_token, run_make

app = typer.Typer(help="Run coordinator container")


@app.command()
def run(
    cpus: Annotated[int | None, typer.Option("--cpus", help="CPU count")] = None,
    memory: Annotated[str | None, typer.Option("--memory", help="Memory limit (e.g. 12G)")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Container name")] = None,
) -> None:
    """Run an interactive coordinator shell (hands off TTY)."""
    check_token()
    make_vars: dict[str, str] = {}
    if cpus is not None:
        make_vars["CPUS"] = str(cpus)
    if memory:
        make_vars["MEMORY"] = memory
    if name:
        make_vars["NAME"] = name
    run_make(Target.RUN, make_vars, tty=True)


@app.command()
def shell(
    cpus: Annotated[int | None, typer.Option("--cpus", help="CPU count")] = None,
    memory: Annotated[str | None, typer.Option("--memory", help="Memory limit (e.g. 12G)")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Container name")] = None,
) -> None:
    """Alias for run — open an interactive shell in the coordinator container."""
    check_token()
    make_vars: dict[str, str] = {}
    if cpus is not None:
        make_vars["CPUS"] = str(cpus)
    if memory:
        make_vars["MEMORY"] = memory
    if name:
        make_vars["NAME"] = name
    run_make(Target.SHELL, make_vars, tty=True)
