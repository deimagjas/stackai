"""Bridge network management command.

Registered as a top-level command by `container_cli.main`.
"""

from typing import Annotated

import typer

from container_cli.targets import Target
from container_cli.utils import run_make


def network(
    subnet: Annotated[str | None, typer.Option("--subnet", help="Subnet CIDR")] = None,
    network_name: Annotated[str | None, typer.Option("--network-name", help="Network name")] = None,
) -> None:
    """Create the isolated bridge network."""
    make_vars: dict[str, str] = {}
    if subnet:
        make_vars["SUBNET"] = subnet
    if network_name:
        make_vars["NETWORK"] = network_name
    run_make(Target.NETWORK, make_vars)
