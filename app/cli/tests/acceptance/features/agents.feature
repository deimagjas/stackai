Feature: Agent lifecycle commands
  As a user of the q CLI
  I want to inspect and manage running agents
  So that I can monitor and control my work

  Background:
    Given the make runner is ready

  Scenario: List active agents
    When I run "q agents list"
    Then the command exits successfully
    And the make runner was invoked with target "list-agents"

  Scenario: Show status when status file exists
    Given a status file exists for branch "feat/foo" with payload {"phase": "running"}
    When I run "q agents status --branch feat/foo"
    Then the command exits successfully
    And the output contains "running"

  Scenario: Show status when status file is missing
    When I run "q agents status --branch feat/missing"
    Then the command exits with an error
    And the output contains "No status file found"

  Scenario: Stop an agent by branch
    When I run "q agents stop --branch feat/foo"
    Then the command exits successfully
    And the make runner was invoked with target "stop-agent"
    And the make vars include BRANCH="feat/foo"
