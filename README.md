# Clio MCP Server

MCP server that exposes [Clio's](https://www.clio.com/) practice management API as tools for AI assistants.

> 🚧 Under active development

## Quick start

```bash
uv sync
cp .env.example .env
# Fill in your Clio API credentials and Anthropic key
uv run python -m clio_mcp.server
```

## Tools

_Coming soon_

## Architecture

_Coming soon_

## Data handling

This server runs locally over stdio; no data transits through any infrastructure operated by this project's author. Tool responses flow from the Clio API to the local process to the user's Claude client, subject to that client's data handling terms. Observability is via self-hosted [Arize Phoenix](https://phoenix.arize.com/); traces do not leave the user's machine.