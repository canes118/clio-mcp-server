# Evals

## What this is

An eval harness for the Clio MCP server. The harness launches the server
as a stdio subprocess, uses the Anthropic SDK to drive Claude with the
server's tools attached, and observes how Claude selects tools and
constructs arguments in response to a prompt.

## What "eval" means here

Quantitative measurement of tool selection and argument construction —
*which* tool the model picks, with *what* arguments, on *which* turn —
not just "did it produce a reasonable-looking answer." Each run over
the committed `CASES` list scores three booleans per case
(`tool_match`, `args_match`, `completed`) and persists the full
capture as JSON under `evals/runs/` (gitignored).

## Running

Run from the repo root (not from `evals/`):

```bash
uv run --group evals python -m evals.harness
uv run --group evals python -m evals.harness --query "find contacts named Smith"
```

With no arguments, the harness runs the committed `CASES` list from
`evals/cases.py`, scores each result, prints a plain-text summary
table, and writes the full run to `evals/runs/{timestamp}-{sha}.json`.
`--query` is an ad-hoc override for exploration — it builds a single
unscored case on the fly; scoring will fail on it by design.

Requires `ANTHROPIC_API_KEY` in `.env`. The harness spawns the server
as a subprocess, which needs authenticated Clio tokens — run
`uv run python -m clio_mcp.auth` once beforehand if you haven't already.
The server subprocess inherits the harness's environment, so `CLIO_*`
vars propagate automatically.

## Architecture

Deliberately a hand-rolled agent loop rather than the Anthropic SDK's
built-in MCP connector: at each step the harness calls
`client.messages.create()`, inspects each `tool_use` block in the
response, invokes the corresponding tool via the MCP `ClientSession`,
and appends `tool_result` blocks to the conversation. It loops until
`stop_reason == "end_turn"` (capped at 5 iterations). The explicit loop
gives per-step visibility — tool name, arguments, result, latency — which
is what the upcoming metrics layer will hook into.
