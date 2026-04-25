# Makefile for Python CLI mutation testing

.PHONY: mutation-run mutation-show mutation-results mutation-run-file mutation-clean

# Run the full mutation suite
mutation-run:
	uv run mutmut run

# Display mutation results/diffs
mutation-show:
	uv run mutmut show

# Show mutation score summary
mutation-results:
	uv run mutmut results

# Run mutations on a specific file
# Usage: make mutation-run-file FILE=path/to/file.py
mutation-run-file:
	uv run mutmut run --paths-to-mutate $(FILE)

# Reset the mutmut state/cache and remove generated artifacts
mutation-clean:
	rm -rf mutants/ .mutmut-cache
