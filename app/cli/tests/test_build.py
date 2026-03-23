from __future__ import annotations

from container_cli.commands.build import build, clean, clean_all, clean_network


class TestBuild:
    def test_no_options(self, mock_run_make):
        build(image=None, dockerfile=None)
        mock_run_make["build"].assert_called_once_with("build", {})

    def test_with_image(self, mock_run_make):
        build(image="my-image:v1", dockerfile=None)
        mock_run_make["build"].assert_called_once_with("build", {"IMAGE": "my-image:v1"})

    def test_with_dockerfile(self, mock_run_make):
        build(image=None, dockerfile="Dockerfile.dev")
        mock_run_make["build"].assert_called_once_with("build", {"DOCKERFILE": "Dockerfile.dev"})

    def test_with_both_options(self, mock_run_make):
        build(image="img", dockerfile="Dockerfile.prod")
        mock_run_make["build"].assert_called_once_with(
            "build", {"IMAGE": "img", "DOCKERFILE": "Dockerfile.prod"}
        )


class TestClean:
    def test_clean(self, mock_run_make):
        clean()
        mock_run_make["build"].assert_called_once_with("clean")


class TestCleanNetwork:
    def test_clean_network(self, mock_run_make):
        clean_network()
        mock_run_make["build"].assert_called_once_with("clean-network")


class TestCleanAll:
    def test_clean_all(self, mock_run_make):
        clean_all()
        mock_run_make["build"].assert_called_once_with("clean-all")
