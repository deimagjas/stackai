# CLAUDE.md

## Documentation

When implementing a new feature, always update the relevant documentation in `docs/`.

- If the feature affects container behavior, image build, or the entrypoint: update `docs/agents/container-agent.md`
- If the feature affects how agents are spawned or monitored: update `docs/agents/spawn-agent-skill.md`
- If the feature adds or changes CLI commands in `app/cli/`: update `docs/agents/cli.md`
- If a new subsystem is introduced with no existing doc, create a new file under the appropriate `docs/` subdirectory

Documentation should reflect the current state of the code. Keep troubleshooting tables and flow descriptions in sync with the actual implementation.
