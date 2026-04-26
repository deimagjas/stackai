Feature: Bridge network management
  As a user of the q CLI
  I want to create the bridge network
  So that agent containers can communicate

  Background:
    Given the make runner is ready

  Scenario: Create network with defaults
    When I run "q network"
    Then the command exits successfully
    And the make runner was invoked with target "network"

  Scenario: Create network with custom subnet
    When I run "q network --subnet 10.0.0.0/24 --network-name custom-net"
    Then the command exits successfully
    And the make vars include SUBNET="10.0.0.0/24" and NETWORK="custom-net"
