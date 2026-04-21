"""FastMCP server entry point for Clio MCP."""

from dotenv import load_dotenv
from fastmcp import FastMCP

from clio_mcp.tools.matters import get_matter, search_matters

mcp = FastMCP("clio-mcp-server")

mcp.add_tool(get_matter)
mcp.add_tool(search_matters)


def main() -> None:
    load_dotenv()
    mcp.run()


if __name__ == "__main__":
    main()
