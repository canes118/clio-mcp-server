from __future__ import annotations

import json
import os
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

import platformdirs
import pydantic

from clio_mcp.auth.exceptions import ClioTokenFileCorruptError
from clio_mcp.auth.models import ClioTokens


class TokenStore(ABC):
    """Abstract interface for persisting OAuth tokens."""

    @abstractmethod
    def load(self) -> ClioTokens | None:
        """Load tokens from storage. Returns None if no tokens exist."""

    @abstractmethod
    def save(self, tokens: ClioTokens) -> None:
        """Persist tokens to storage."""

    @abstractmethod
    def clear(self) -> None:
        """Remove stored tokens."""


class FileTokenStore(TokenStore):
    """Stores tokens as JSON on the local filesystem."""

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path = path or (
            platformdirs.user_config_path("clio-mcp") / "tokens.json"
        )

    def load(self) -> ClioTokens | None:
        if not self.path.exists():
            return None

        text = self.path.read_text(encoding="utf-8")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ClioTokenFileCorruptError(
                f"Token file at {self.path} contains invalid JSON"
            ) from exc

        try:
            return ClioTokens.model_validate(data)
        except pydantic.ValidationError as exc:
            raise ClioTokenFileCorruptError(
                f"Token file at {self.path} failed validation: {exc}"
            ) from exc

    def save(self, tokens: ClioTokens) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file in same directory, then replace
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".tokens_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(tokens.model_dump_json(indent=2))
            os.replace(tmp_path, self.path)
        except BaseException:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        # Restrict permissions to owner only (skip on Windows)
        if sys.platform != "win32":
            self.path.chmod(0o600)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
