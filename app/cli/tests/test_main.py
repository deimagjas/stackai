from __future__ import annotations

from typer.testing import CliRunner

from container_cli.main import app

runner = CliRunner()


class TestAppStructure:
    def test_has_build_command(self):
        names = [cmd.name for cmd in app.registered_commands]
        assert "build" in names

    def test_has_spawn_command(self):
        names = [cmd.name for cmd in app.registered_commands]
        assert "spawn" in names

    def test_has_run_and_shell_commands(self):
        names = [cmd.name for cmd in app.registered_commands]
        assert "run" in names
        assert "shell" in names

    def test_has_agents_subapp(self):
        group_names = [g.name for g in app.registered_groups]
        assert "agents" in group_names

    def test_has_pi_subapp(self):
        group_names = [g.name for g in app.registered_groups]
        assert "pi" in group_names


class TestHelp:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Container management CLI" in result.output
