"""FastMCP server entry point for Clio MCP."""

from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP  # noqa: E402

from clio_mcp.tools.matters import get_matter, search_matters  # noqa: E402

mcp = FastMCP("clio-mcp-server")

mcp.add_tool(get_matter)
mcp.add_tool(search_matters)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
