from typing import Annotated

import typer

from container_cli.utils import run_make

app = typer.Typer(help="Network management commands")


@app.command()
def network(
    subnet: Annotated[str | None, typer.Option("--subnet", help="Subnet CIDR")] = None,
    network_name: Annotated[str | None, typer.Option("--network-name", help="Network name")] = None,
) -> None:
    """Create the isolated bridge network."""
    vars: dict[str, str] = {}
    if subnet:
        vars["SUBNET"] = subnet
    if network_name:
        vars["NETWORK"] = network_name
    run_make("network", vars)
