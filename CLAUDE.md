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

## Do not

- Do not add LangGraph, LangChain, or any agent framework. This is a
  tool server, not an agent.
- Do not build a web UI. This is stdio transport, consumed by Claude
  Desktop or an eval harness.
- Do not use the raw MCP Python SDK. Use FastMCP.
- Do not commit `.env` or any file containing API keys.
- Do not modify files in `evals/` when I ask you to work on tools or
  the client. These are separate concerns.

## Running

```bash
uv run python -m clio_mcp.server        # start server (stdio)
uv run pytest                            # run tests
uv run python evals/eval_runner.py       # run eval harness
```

## Key references

- Clio API docs: https://docs.developers.clio.com/
- FastMCP: https://github.com/jlowin/fastmcp
- MCP spec: https://modelcontextprotocol.io
