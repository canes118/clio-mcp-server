"""Exceptions raised by the Clio main-API client."""

from __future__ import annotations


class ClioAPIError(Exception):
    """Base for all Clio main-API errors. Carries the HTTP status code
    and response body so callers can inspect what went wrong.
    """

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Clio API error ({status_code}): {body}")


class ClioNotFoundError(ClioAPIError):
    """Raised on 404 responses so tools can handle a missing resource
    (e.g. "matter not found") separately from other API failures.
    """
