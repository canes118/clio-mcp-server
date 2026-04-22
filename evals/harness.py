"""Hand-rolled Anthropic-SDK-as-MCP-client eval harness.

Launches the Clio MCP server as a stdio subprocess, exposes its tools
to Claude via the Anthropic Messages API, and runs a single scenario
through an explicit agent loop. Skeleton only — no metrics, no result
storage, no scenario library yet.
"""

import argparse
import asyncio
import json
import sys

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

load_dotenv()

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024
MAX_ITERATIONS = 5
DEFAULT_QUERY = "find matters matching 'Acme'"


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


async def run_scenario(session: ClientSession, query: str) -> None:
    tools_response = await session.list_tools()
    mcp_tools = tools_response.tools
    print("Available tools:", [t.name for t in mcp_tools])

    anthropic_tools = [_mcp_tool_to_anthropic(t) for t in mcp_tools]
    client = AsyncAnthropic()
    messages: list[dict] = [{"role": "user", "content": query}]

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"Iteration {iteration}:")
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=anthropic_tools,
        )

        tool_results: list[dict] = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"Tool call: {block.name} {json.dumps(block.input)}")
                result = await session.call_tool(block.name, block.input)
                result_text = _format_tool_result(result)
                print(f"Tool result: {result_text}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                        "is_error": result.isError,
                    }
                )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            print(f"Final response: {final_text}")
            return

        if not tool_results:
            print(
                f"No tool_use blocks and stop_reason={response.stop_reason!r}; stopping."
            )
            return

        messages.append({"role": "user", "content": tool_results})

    print(f"Reached max iterations ({MAX_ITERATIONS}) without end_turn; stopping.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Clio MCP eval harness skeleton.")
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"User prompt to send to Claude. Default: {DEFAULT_QUERY!r}",
    )
    args = parser.parse_args()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "clio_mcp.server"],
    )

    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        await run_scenario(session, args.query)


if __name__ == "__main__":
    asyncio.run(main())
