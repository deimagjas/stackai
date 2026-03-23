from __future__ import annotations

from container_cli.commands.run import run, shell


class TestRun:
    def test_calls_check_token(self, mock_run_make, mock_check_token):
        run(cpus=None, memory=None, name=None)
        mock_check_token["run"].assert_called_once()

    def test_basic_run(self, mock_run_make, mock_check_token):
        run(cpus=None, memory=None, name=None)
        mock_run_make["run"].assert_called_once_with("run", {}, tty=True)

    def test_run_with_cpus(self, mock_run_make, mock_check_token):
        run(cpus=4, memory=None, name=None)
        call_vars = mock_run_make["run"].call_args[0][1]
        assert call_vars["CPUS"] == "4"

    def test_run_with_memory_and_name(self, mock_run_make, mock_check_token):
        run(cpus=None, memory="16G", name="coord")
        call_vars = mock_run_make["run"].call_args[0][1]
        assert call_vars == {"MEMORY": "16G", "NAME": "coord"}

    def test_tty_always_true(self, mock_run_make, mock_check_token):
        run(cpus=None, memory=None, name=None)
        assert mock_run_make["run"].call_args[1]["tty"] is True


class TestShell:
    def test_calls_check_token(self, mock_run_make, mock_check_token):
        shell(cpus=None, memory=None, name=None)
        mock_check_token["run"].assert_called_once()

    def test_basic_shell(self, mock_run_make, mock_check_token):
        shell(cpus=None, memory=None, name=None)
        mock_run_make["run"].assert_called_once_with("shell", {}, tty=True)

    def test_shell_with_all_options(self, mock_run_make, mock_check_token):
        shell(cpus=8, memory="32G", name="dev")
        mock_run_make["run"].assert_called_once_with(
            "shell", {"CPUS": "8", "MEMORY": "32G", "NAME": "dev"}, tty=True
        )
