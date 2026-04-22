# Clio MCP Server

MCP server exposing Clio's practice management API as tools for AI
assistants. Built with FastMCP. Local stdio transport only.

## Stack

- Python 3.13, uv
- FastMCP (not the raw MCP reference SDK)
- Pydantic v2 for all data models
- httpx for async HTTP (Clio API client)
- pytest for tests, no pytest plugins unless necessary

## Project layout

- `src/clio_mcp/server.py` — FastMCP server instance, tool registration
- `src/clio_mcp/client.py` — Clio API client (all HTTP calls go through here)
- `src/clio_mcp/models.py` — Pydantic models for Clio entities
- `src/clio_mcp/auth.py` — OAuth2 handling
- `src/clio_mcp/tools/` — one module per Clio domain (matters, contacts, billing, tasks)
- `evals/` — eval harness (separate from tests, uses Anthropic SDK as MCP client)
- `tests/` — pytest unit/integration tests

## Conventions

- All Clio API responses must be validated through Pydantic models before
  being returned as tool results. Never return raw dicts from tools.
- Tool functions go in `src/clio_mcp/tools/`. Each tool function gets
  the `@mcp.tool()` decorator and a clear docstring — the docstring IS
  the tool description the LLM sees, so write it for an attorney end
  user, not a developer.
- HTTP calls to Clio go through `client.py`, never directly from tools.
  Tools call client methods, client handles auth, retries, and rate limits.
- Type hints on every function signature. No `Any` unless truly necessary.
- Tests mirror the src structure: `tests/test_tools/test_matters.py`
  tests `src/clio_mcp/tools/matters.py`.

## Commits

- Conventional Commits format: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`. Scope in parens where useful: `feat(matters): add search_matters tool`.
- Run `uv run pytest` before every commit. Do not commit on red.
- No Claude co-author trailer. Do not append `Co-Authored-By: Claude <noreply@anthropic.com>` or any similar trailer. Commits are authored by you only.

## Do not

- Do not add LangGraph, LangChain, or any agent framework. This is a
  tool server, not an agent.
- Do not build a web UI. This is stdio transport, consumed by Claude
  Desktop or an eval harness.
- Do not use the raw MCP Python SDK. Use FastMCP.
- Do not commit `.env` or any file containing API keys.
- Do not cross-modify between `src/` + `tests/` and `evals/` in a
  single PR. Evals changes go in their own PRs; server and tool
  changes stay out of `evals/`.

## Confidentiality and data handling

This repo is public. The following must not appear in any committed file, commit message, PR title, PR body, or issue:

- Real client names, firm names, matter names, or matter display numbers
- Real contact names (attorneys, staff, opposing counsel)
- Real IDs that could be linked back to actual Clio records
- Environment-specific identifiers (sandbox names, workspace names)

In examples, docstrings, tests, and fixtures, use generic placeholders: "Acme", "Smith", "Example LLC". Test data is synthetic.

Before committing, grep the diff for anything that looks like a proper noun you didn't invent. Pre-commit hooks will not catch this — it's a human judgment check.

The server runs against live Clio data. Treat all tool inputs and
outputs as sensitive downstream of the machine. This applies to every
run mode: `fastmcp dev` smoke tests, eval harness runs, and Claude
Desktop dogfooding.

- Do not paste raw server output, eval traces, or Phoenix screenshots
  into commits, PRs, issues, blog posts, or chat conversations without
  redaction.
- Eval harness output defaults to redacted. A `redact()` helper lives
  in the harness; every print/log call site goes through it. Raw mode
  is opt-in and local-only.
- Committed eval scenarios must not reference real matters or clients.
  Use generic prompts ("find the most recently created matter") or
  synthetic placeholders.
- Published artifacts (README, blog posts, talks, PR descriptions)
  reference aggregate metrics and methodology. Individual scenario
  inputs and outputs are not published.

Anthropic API traffic (tool calls and results sent to api.anthropic.com
as part of normal operation) is inherent to the integration pattern
and has been considered. This section governs downstream artifacts
that leave the machine in human-readable form.

## Running

```bash
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg  # first-time setup
uv run python -m clio_mcp.server        # start server (stdio)
uv run pytest                            # run tests
uv run --group evals python -m evals.harness  # run eval harness (requires ANTHROPIC_API_KEY)
```

## Key references

- Clio API docs: https://docs.developers.clio.com/
- FastMCP: https://github.com/jlowin/fastmcp
- MCP spec: https://modelcontextprotocol.io
