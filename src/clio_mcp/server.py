"""FastMCP server entry point for Clio MCP."""

from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP  # noqa: E402

from clio_mcp.observability import setup_tracing  # noqa: E402
from clio_mcp.tools.contacts import get_contact, search_contacts  # noqa: E402
from clio_mcp.tools.matters import get_matter, search_matters  # noqa: E402

mcp = FastMCP("clio-mcp-server")

mcp.add_tool(get_matter)
mcp.add_tool(search_matters)
mcp.add_tool(get_contact)
mcp.add_tool(search_contacts)


def main() -> None:
    setup_tracing()
    mcp.run()


if __name__ == "__main__":
    main()
