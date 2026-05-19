# AGENTS.md

## Project context strategy

Before starting any coding task, first inspect the project context files in this order:

1. `graphify-out/GRAPH_REPORT.md`
2. `graphify-out/graph.json`
3. `README.md`
4. Relevant files from `src/`, `ui/`, or `tests/` only after identifying them from the graph/report.

Do not scan the entire repository unless the user explicitly asks for a full project review.

## Token-saving rules

- Open only files directly related to the current task.
- Before editing, list the files you plan to inspect and explain why.
- Prefer small, focused changes over broad refactors.
- Do not refactor unrelated code.
- If more than 5 files need to be opened, explain why first.
- If `graphify-out/GRAPH_REPORT.md` is missing or outdated, tell the user to regenerate it with `graphify .`.

## Project structure

Main folders:

- `src/` — backend / Python application logic
- `ui/` — user interface
- `tests/` — tests
- `data/` — local data or memory files
- `graphify-out/` — generated project graph and reports

## After changes

After significant code changes:

1. Summarize what changed.
2. Mention which files were modified.
3. Suggest whether the graph should be regenerated with:

```bash
graphify .