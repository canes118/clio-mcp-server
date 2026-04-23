"""Hand-rolled Anthropic-SDK-as-MCP-client eval harness.

Launches the Clio MCP server as a stdio subprocess, exposes its tools
to Claude via the Anthropic Messages API, and runs cases through an
explicit agent loop. Per-case output is returned as a `CaseResult`
(see evals/cases.py) so downstream layers can score and persist it.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from evals.cases import CaseResult, TestCase, TurnRecord

load_dotenv()

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024
MAX_ITERATIONS = 5
DEFAULT_QUERY = "find matters matching 'Acme'"
RUNS_DIR = Path(__file__).parent / "runs"


def _mcp_tool_to_anthropic(tool: types.Tool) -> dict:
    """Convert an MCP tool definition to Anthropic's tool schema shape."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


def _format_tool_result(result: types.CallToolResult) -> str:
    """Flatten an MCP tool result's content blocks into a single string."""
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
        else:
            parts.append(block.model_dump_json())
    return "\n".join(parts)


async def run_case(
    case: TestCase, session: ClientSession, client: AsyncAnthropic
) -> CaseResult:
    """Run one case through the agent loop and return the full capture.

    Preserves the existing loop semantics: 5-iteration cap, `tool_use` →
    `call_tool` relay, termination on `stop_reason == "end_turn"`. Each
    tool invocation is captured as a `TurnRecord` with the raw tool
    result and per-call latency; wall-clock time and final text are
    recorded on the returned `CaseResult`. Scoring is intentionally not
    performed here — `result.scores` is left empty for `score()` to
    fill in.
    """
    start = time.perf_counter()

    tools_response = await session.list_tools()
    mcp_tools = tools_response.tools
    anthropic_tools = [_mcp_tool_to_anthropic(t) for t in mcp_tools]

    messages: list[dict] = [{"role": "user", "content": case.query}]
    turns: list[TurnRecord] = []
    final_text = ""
    completed = False
    iterations = 0

    for iteration in range(1, MAX_ITERATIONS + 1):
        iterations = iteration
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=anthropic_tools,
        )

        tool_results: list[dict] = []
        for block in response.content:
            if block.type == "tool_use":
                call_started = time.perf_counter()
                result = await session.call_tool(block.name, block.input)
                latency_ms = (time.perf_counter() - call_started) * 1000
                turns.append(
                    TurnRecord(
                        tool_name=block.name,
                        tool_args=dict(block.input),
                        tool_result=result.model_dump(mode="json"),
                        latency_ms=latency_ms,
                    )
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _format_tool_result(result),
                        "is_error": result.isError,
                    }
                )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            completed = True
            break

        if not tool_results:
            break

        messages.append({"role": "user", "content": tool_results})

    wall_time_ms = (time.perf_counter() - start) * 1000

    return CaseResult(
        case_name=case.name,
        prompt=case.query,
        turns=turns,
        final_text=final_text,
        iterations=iterations,
        wall_time_ms=wall_time_ms,
        completed=completed,
    )


def score(case: TestCase, result: CaseResult) -> dict[str, bool]:
    """Score a CaseResult against its TestCase expectations.

    Returns three booleans:

    - ``tool_match``: the first tool call matches ``case.expected_tool``.
    - ``args_match``: every ``(k, v)`` in ``case.expected_args_subset``
      is present in the first call's arguments with the expected value.
      Subset semantics — extra valid args in the actual call do not
      fail the check; a missing key or mismatched value does.
    - ``completed``: copy of ``result.completed``.

    If ``result.turns`` is empty, both ``tool_match`` and ``args_match``
    are False. Mutates ``result.scores`` in place and returns the same
    dict for convenience at the call site.
    """
    if not result.turns:
        tool_match = False
        args_match = False
    else:
        first = result.turns[0]
        tool_match = first.tool_name == case.expected_tool
        args_match = all(
            k in first.tool_args and first.tool_args[k] == v
            for k, v in case.expected_args_subset.items()
        )

    scores = {
        "tool_match": tool_match,
        "args_match": args_match,
        "completed": result.completed,
    }
    result.scores = scores
    return scores


def _short_git_sha() -> str:
    """Return ``git rev-parse --short HEAD`` or ``"nogit"`` on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"
    return result.stdout.strip() or "nogit"


def persist_run(
    results: list[CaseResult],
    runs_dir: Path,
    model: str,
    started_at: datetime,
) -> Path:
    """Write a run as a single JSON file and return its path.

    Filename is ``{YYYYMMDD-HHMMSS}-{short_sha}.json`` using the
    finished-at timestamp. ``runs_dir`` is created if missing. If git
    is unavailable, the SHA slot falls back to ``"nogit"`` rather than
    crashing the harness.

    Case payloads go through ``CaseResult.model_dump(mode="json")`` so
    nested Pydantic models and other JSON-tricky types serialize
    cleanly. Summary counters reflect the scores already populated by
    ``score()``; callers are expected to have scored each result before
    calling this function.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)

    git_sha = _short_git_sha()
    finished_at = datetime.now(timezone.utc)
    run_id = f"{finished_at.strftime('%Y%m%d-%H%M%S')}-{git_sha}"

    tool_match_passes = sum(1 for r in results if r.scores.get("tool_match"))
    args_match_passes = sum(1 for r in results if r.scores.get("args_match"))
    completed_passes = sum(1 for r in results if r.scores.get("completed"))
    all_passed = sum(
        1
        for r in results
        if all(r.scores.get(k) for k in ("tool_match", "args_match", "completed"))
    )

    payload = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "git_sha": git_sha,
        "model": model,
        "cases": [r.model_dump(mode="json") for r in results],
        "summary": {
            "total": len(results),
            "tool_match_passes": tool_match_passes,
            "args_match_passes": args_match_passes,
            "completed_passes": completed_passes,
            "all_passed": all_passed,
        },
    }

    path = runs_dir / f"{run_id}.json"
    with path.open("w") as f:
        json.dump(payload, f, indent=2)
    return path


async def main() -> None:
    parser = argparse.ArgumentParser(description="Clio MCP eval harness.")
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=(
            "Ad-hoc prompt to send to Claude. Default: "
            f"{DEFAULT_QUERY!r}. (CASES wiring arrives in a follow-up commit.)"
        ),
    )
    args = parser.parse_args()

    case = TestCase(
        name="adhoc",
        query=args.query,
        expected_tool="",
        expected_args_subset={},
    )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "clio_mcp.server"],
    )

    client = AsyncAnthropic()

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await run_case(case, session, client)

    for turn in result.turns:
        print(f"Tool call: {turn.tool_name} {turn.tool_args}")
    if result.final_text:
        print(f"Final response: {result.final_text}")
    if not result.completed:
        print(
            f"Stopped without end_turn after {result.iterations} "
            f"iteration(s) (cap={MAX_ITERATIONS})."
        )


if __name__ == "__main__":
    asyncio.run(main())
