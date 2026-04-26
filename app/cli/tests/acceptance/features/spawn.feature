Feature: Spawn agent containers
  As a user of the q CLI
  I want to spawn agent containers for branches
  So that I can delegate work to isolated environments

  Background:
    Given the make runner is ready

  Scenario: Spawn an agent with a valid token
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is set
    When I run "q spawn --branch feat/foo --task implement-x"
    Then the command exits successfully
    And the make runner was invoked with target "spawn"
    And the make vars include BRANCH="feat/foo" and TASK="implement-x"

  Scenario: Spawn fails when no token is configured
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is not set
    When I run "q spawn --branch feat/foo --task implement-x"
    Then the command exits with an error
    And the output mentions the missing token

  Scenario: Spawn with custom resources
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is set
    When I run "q spawn --branch feat/bar --task work --cpus 8 --memory 16G --image custom:tag"
    Then the command exits successfully
    And the make vars include CPUS="8" and MEMORY="16G" and IMAGE="custom:tag"
