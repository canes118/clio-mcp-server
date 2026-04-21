"""OAuth2 bootstrap flow: opens browser, captures callback, exchanges code."""

from __future__ import annotations

import secrets
import threading
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from clio_mcp.auth.client import ClioAuthClient
from clio_mcp.auth.exceptions import ClioAuthError
from clio_mcp.auth.models import ClioConfig, ClioTokens
from clio_mcp.auth.token_store import TokenStore

_SUCCESS_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Clio MCP — Authorized</title></head>
<body>
<h1>Authorization successful!</h1>
<p>You can close this tab and return to your terminal.</p>
</body>
</html>
"""


class _CallbackHandler(BaseHTTPRequestHandler):
    """One-shot HTTP handler that captures the OAuth callback."""

    def do_GET(self) -> None:
        qs = parse_qs(urlparse(self.path).query)
        code = qs.get("code", [None])[0]  # type: ignore[list-item]
        state = qs.get("state", [None])[0]  # type: ignore[list-item]

        self.server.callback_code = code  # type: ignore[attr-defined]
        self.server.callback_state = state  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(_SUCCESS_HTML.encode())

        self.server.callback_event.set()  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        # Suppress default stderr logging
        pass


async def bootstrap(
    config: ClioConfig,
    store: TokenStore,
    client: ClioAuthClient,
    port: int = 8765,
    timeout: float = 300.0,
) -> ClioTokens:
    """Run the interactive OAuth2 bootstrap flow.

    Opens a browser for the user to authorize, captures the callback on
    localhost, exchanges the code for tokens, and saves them.

    Raises ClioAuthError on timeout or state mismatch.
    """
    state = secrets.token_urlsafe(32)
    authorize_url = client.build_authorize_url(state)

    event = threading.Event()
    server = HTTPServer(("127.0.0.1", port), partial(_CallbackHandler))
    server.callback_code = None  # type: ignore[attr-defined]
    server.callback_state = None  # type: ignore[attr-defined]
    server.callback_event = event  # type: ignore[attr-defined]

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        webbrowser.open(authorize_url)

        arrived = event.wait(timeout=timeout)
        if not arrived:
            raise ClioAuthError(
                f"Timed out waiting for OAuth callback after {timeout} seconds. "
                "Please try again."
            )

        callback_state = server.callback_state  # type: ignore[attr-defined]
        callback_code = server.callback_code  # type: ignore[attr-defined]

        if callback_state != state:
            raise ClioAuthError(
                "OAuth state mismatch — possible CSRF attack. "
                "Please try the authorization flow again."
            )

        if not callback_code:
            raise ClioAuthError(
                "No authorization code received in the callback. "
                "The user may have denied the request."
            )

        tokens = await client.exchange_code(callback_code)
        store.save(tokens)
        return tokens

    finally:
        server.shutdown()
        server_thread.join(timeout=5.0)
