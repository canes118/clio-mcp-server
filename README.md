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

## Contributing / Local setup

```bash
uv sync --group dev          # install dev dependencies (includes pre-commit)
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

cp .client-names.example .client-names
# Edit .client-names to list client names the hook should block.
```

The `block-client-names` pre-commit hook reads `.client-names` (gitignored) and refuses commits that contain any listed name as a case-insensitive whole-word match. The denylist is per-clone and must be populated locally; `.client-names.example` documents the format. The hook is defense-in-depth — see the confidentiality section of `CLAUDE.md` for the broader rules.

## Data handling

This server runs locally over stdio; no data transits through any infrastructure operated by this project's author. Tool responses flow from the Clio API to the local process to the user's Claude client, subject to that client's data handling terms. Observability is via self-hosted [Arize Phoenix](https://phoenix.arize.com/); traces do not leave the user's machine.