"""CLI entry point: python -m clio_mcp.auth

Runs the OAuth2 bootstrap flow to obtain and store tokens.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from clio_mcp.auth.bootstrap import bootstrap
from clio_mcp.auth.client import ClioAuthClient
from clio_mcp.auth.exceptions import ClioAuthError
from clio_mcp.auth.models import ClioConfig
from clio_mcp.auth.token_store import FileTokenStore


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Authorize Clio MCP server via OAuth2 browser flow."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local port for the OAuth callback server (default: 8765)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for the OAuth callback (default: 300)",
    )
    args = parser.parse_args()

    try:
        config = ClioConfig.from_env()
    except ClioAuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "Hint: create a .env file with CLIO_CLIENT_ID, "
            "CLIO_CLIENT_SECRET, and CLIO_REDIRECT_URI.",
            file=sys.stderr,
        )
        sys.exit(1)

    store = FileTokenStore()
    client = ClioAuthClient(config)

    try:
        asyncio.run(
            bootstrap(config, store, client, port=args.port, timeout=args.timeout)
        )
    except ClioAuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Authorization successful! Tokens saved to {store.path}")


if __name__ == "__main__":
    main()
