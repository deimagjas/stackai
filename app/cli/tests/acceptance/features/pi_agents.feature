Feature: PI agent lifecycle
  As a user of the q CLI
  I want to spawn and manage PI agents backed by the local mlx_lm.server
  So that I can run agents without using cloud LLM credits

  Background:
    Given the make runner is ready

  Scenario: Spawn a PI agent
    When I run "q pi spawn --branch pi/refactor --task rename-helpers"
    Then the command exits successfully
    And the make runner was invoked with target "spawn-pi"
    And the make vars include BRANCH="pi/refactor" and TASK="rename-helpers"

  Scenario: Spawn does not require CLAUDE_CONTAINER_OAUTH_TOKEN
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is not set
    When I run "q pi spawn --branch pi/refactor --task rename-helpers"
    Then the command exits successfully
    And the make runner was invoked with target "spawn-pi"

  Scenario: Spawn with custom resources and backend URL
    When I run "q pi spawn --branch pi/refactor --task work --cpus 4 --memory 8G --base-url http://10.0.0.5:9000/v1"
    Then the command exits successfully
    And the make vars include CPUS="4" and MEMORY="8G" and PI_BASE_URL="http://10.0.0.5:9000/v1"

  Scenario: List PI agents
    When I run "q pi list"
    Then the command exits successfully
    And the make runner was invoked with target "list-pi-agents"

  Scenario: Follow PI agent logs
    When I run "q pi follow --branch pi/refactor"
    Then the command exits successfully
    And the make runner was invoked with target "follow-pi-agent"
    And the make vars include BRANCH="pi/refactor"

  Scenario: Stop a PI agent
    When I run "q pi stop --branch pi/refactor"
    Then the command exits successfully
    And the make runner was invoked with target "stop-pi-agent"
    And the make vars include BRANCH="pi/refactor"

  Scenario: Build the PI image
    When I run "q pi build"
    Then the command exits successfully
    And the make runner was invoked with target "build-pi"

  Scenario: PI status fails when no status file exists
    When I run "q pi status --branch pi/refactor"
    Then the command exits with an error
    And the output contains "No status file found"

  Scenario: PI status reads the persisted status.json
    Given a PI status file exists for branch "pi/refactor" with payload {"phase":"completed","agent_kind":"pi","exit_code":0}
    When I run "q pi status --branch pi/refactor"
    Then the command exits successfully
    And the output contains "completed"
    And the output contains "pi"
