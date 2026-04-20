from __future__ import annotations

import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from clio_mcp.auth.exceptions import ClioTokenFileCorruptError
from clio_mcp.auth.models import ClioTokens
from clio_mcp.auth.token_store import FileTokenStore


@pytest.fixture
def valid_tokens() -> ClioTokens:
    return ClioTokens(
        access_token="access_abc",
        refresh_token="refresh_xyz",
        token_type="bearer",
        expires_at=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    )


@pytest.fixture
def store(tmp_path: Path) -> FileTokenStore:
    return FileTokenStore(path=tmp_path / "tokens.json")


class TestDefaults:
    def test_default_path_includes_clio_mcp(self) -> None:
        store = FileTokenStore()
        assert "clio-mcp" in str(store.path)


class TestLoad:
    def test_returns_none_when_file_missing(self, store: FileTokenStore) -> None:
        assert store.load() is None

    def test_raises_on_invalid_json(self, store: FileTokenStore) -> None:
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("not json at all", encoding="utf-8")
        with pytest.raises(ClioTokenFileCorruptError, match="invalid JSON"):
            store.load()

    def test_raises_on_invalid_schema(self, store: FileTokenStore) -> None:
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        with pytest.raises(ClioTokenFileCorruptError, match="failed validation"):
            store.load()


class TestSave:
    def test_round_trip(
        self, store: FileTokenStore, valid_tokens: ClioTokens
    ) -> None:
        store.save(valid_tokens)
        loaded = store.load()
        assert loaded is not None
        assert loaded.access_token == valid_tokens.access_token
        assert loaded.refresh_token == valid_tokens.refresh_token
        assert loaded.expires_at == valid_tokens.expires_at
        # Verify timezone awareness preserved
        assert loaded.expires_at.tzinfo is not None

    def test_creates_parent_directories(
        self, tmp_path: Path, valid_tokens: ClioTokens
    ) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "tokens.json"
        store = FileTokenStore(path=deep_path)
        store.save(valid_tokens)
        assert deep_path.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not applicable")
    def test_file_permissions_600(
        self, store: FileTokenStore, valid_tokens: ClioTokens
    ) -> None:
        store.save(valid_tokens)
        mode = stat.S_IMODE(store.path.stat().st_mode)
        assert mode == 0o600

    def test_save_leaves_no_temp_file(
        self, store: FileTokenStore, valid_tokens: ClioTokens
    ) -> None:
        store.save(valid_tokens)
        files = list(store.path.parent.iterdir())
        assert all(not f.name.endswith(".tmp") for f in files)

    def test_save_cleans_up_tmp_file_on_failure(
        self,
        store: FileTokenStore,
        valid_tokens: ClioTokens,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import os as _os

        monkeypatch.setattr(_os, "replace", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(RuntimeError, match="boom"):
            store.save(valid_tokens)
        files = list(store.path.parent.iterdir())
        assert all(not f.name.endswith(".tmp") for f in files)


class TestClear:
    def test_deletes_existing_file(
        self, store: FileTokenStore, valid_tokens: ClioTokens
    ) -> None:
        store.save(valid_tokens)
        assert store.path.exists()
        store.clear()
        assert not store.path.exists()

    def test_noop_when_file_missing(self, store: FileTokenStore) -> None:
        # Should not raise
        store.clear()
