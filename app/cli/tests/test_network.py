from __future__ import annotations

from container_cli.commands.network import network


class TestNetwork:
    def test_no_options(self, mock_run_make):
        network(subnet=None, network_name=None)
        mock_run_make["network"].assert_called_once_with("network", {})

    def test_with_subnet(self, mock_run_make):
        network(subnet="10.0.0.0/24", network_name=None)
        mock_run_make["network"].assert_called_once_with("network", {"SUBNET": "10.0.0.0/24"})

    def test_with_network_name(self, mock_run_make):
        network(subnet=None, network_name="my-net")
        mock_run_make["network"].assert_called_once_with("network", {"NETWORK": "my-net"})

    def test_with_both_options(self, mock_run_make):
        network(subnet="172.16.0.0/16", network_name="isolated")
        mock_run_make["network"].assert_called_once_with(
            "network", {"SUBNET": "172.16.0.0/16", "NETWORK": "isolated"}
        )
