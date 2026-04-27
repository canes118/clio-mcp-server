"""Tests for OpenTelemetry tracing setup."""

from __future__ import annotations

import builtins
import importlib
from collections.abc import Iterator

import pytest

from clio_mcp import observability


@pytest.fixture(autouse=True)
def reset_configured_flag() -> Iterator[None]:
    """Reset the module-level configured flag between tests."""
    observability._configured = False
    yield
    observability._configured = False


def test_setup_tracing_handles_missing_otel(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When OTel packages are absent, setup logs a stderr warning and returns."""
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("opentelemetry"):
            raise ImportError(f"mocked missing package: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    observability.setup_tracing()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "OpenTelemetry" in captured.err
    assert "tracing disabled" in captured.err


def test_setup_tracing_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Calling setup_tracing() multiple times only configures once."""
    real_import = builtins.__import__
    import_calls: list[str] = []

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("opentelemetry"):
            import_calls.append(name)
            raise ImportError(f"mocked missing package: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    observability.setup_tracing()
    first_call_imports = list(import_calls)
    first_stderr = capsys.readouterr().err

    observability.setup_tracing()
    second_stderr = capsys.readouterr().err

    assert import_calls == first_call_imports, (
        "second call re-attempted OTel imports; should have short-circuited"
    )
    assert first_stderr != ""
    assert second_stderr == ""


def test_observability_module_imports_without_otel() -> None:
    """The module itself must import even when OTel is unavailable."""
    importlib.reload(observability)
    assert callable(observability.setup_tracing)
