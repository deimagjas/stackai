import typer

from container_cli.commands import agents, build, network, pi_agents, run

app = typer.Typer(name="q", help="Container management CLI for Claude agent containers")
agents_app = agents.app

# Register top-level commands from build module
app.command("build")(build.build)
app.command("clean")(build.clean)
app.command("clean-network")(build.clean_network)
app.command("clean-all")(build.clean_all)

# Register top-level network command
app.command("network")(network.network)

# Register top-level run/shell commands
app.command("run")(run.run)
app.command("shell")(run.shell)

# Register top-level spawn command (delegates to agents.spawn)
app.command("spawn")(agents.spawn)

# Register agents sub-app
app.add_typer(agents_app, name="agents")

# Register PI agent sub-app (extension — local mlx_lm backend, no Claude token)
app.add_typer(pi_agents.app, name="pi")


if __name__ == "__main__":
    app()
