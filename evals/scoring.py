"""Pure scoring logic over captured CaseResult data.

Kept separate from evals/harness.py so that tests and any other
consumer can import it without transitively pulling in the runtime
dependencies (anthropic, mcp) that the harness needs at live-run
time.
"""

from typing import Any

from evals.cases import CaseResult, ExpectedCall, TestCase, TurnRecord


def _extract_payload(tool_result: Any) -> Any:
    """Unwrap an MCP CallToolResult dump down to the tool's actual return.

    FastMCP wraps any non-dict return (lists, discriminated unions) as
    ``{"result": <value>}`` and sets ``meta.fastmcp.wrap_result``. For
    Pydantic models that already serialize to a dict, ``structuredContent``
    holds the model fields directly. This helper hides that distinction
    so result-shape checks see the data the tool returned.
    """
    if not isinstance(tool_result, dict):
        return None
    structured = tool_result.get("structuredContent")
    if structured is None:
        return None
    meta = tool_result.get("meta") or {}
    wrapped = meta.get("fastmcp", {}).get("wrap_result", False)
    if wrapped and isinstance(structured, dict) and "result" in structured:
        return structured["result"]
    return structured


def _args_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(k in actual and actual[k] == v for k, v in expected.items())


def _call_succeeded(turn: TurnRecord) -> bool:
    """A turn succeeded at the MCP protocol level.

    True when ``tool_result`` is a dict with ``isError`` either absent or
    explicitly False. A non-dict result, or any truthy ``isError`` value,
    counts as failure. This is distinct from result_match — a tool that
    returns ``isError: True`` would still pass a vacuous-truth result_match
    (no fields required), so this column is needed to catch protocol-level
    failures the field-level scorer misses.
    """
    if not isinstance(turn.tool_result, dict):
        return False
    return not turn.tool_result.get("isError", False)


def _result_match(turn: TurnRecord, expected: ExpectedCall) -> bool:
    if not expected.non_null_fields:
        return True
    payload = _extract_payload(turn.tool_result)
    # List-shape checks are deliberately out of scope for v1: a non-empty
    # non_null_fields against a list result means the case was configured
    # for a get-by-id-style tool but pointed at a search tool.
    if isinstance(payload, list):
        return False
    if not isinstance(payload, dict):
        return False
    return all(
        field in payload and payload[field] is not None
        for field in expected.non_null_fields
    )


def score(case: TestCase, result: CaseResult) -> dict[str, bool]:
    """Score a CaseResult against its TestCase expectations.

    Trajectory shape comes first: if the actual call count differs from
    ``len(case.expected_calls)``, ``tool_match`` is False and per-call
    scoring is skipped (``args_match`` and ``result_match`` are also
    False). When the lengths match, each ``(actual, expected)`` pair is
    scored positionally and the per-column booleans are aggregated with
    ``all()`` — one boolean per column regardless of trajectory length.

    Returns five booleans:

    - ``tool_match``: every actual call's tool name matches the expected
      call at the same position, AND lengths match.
    - ``args_match``: every ``(k, v)`` in each expected call's
      ``args_subset`` is present in the corresponding actual call's
      arguments with the expected value. Subset semantics — extra args
      in the actual call do not fail the check.
    - ``result_match``: each actual call's payload contains every field
      in the corresponding expected call's ``non_null_fields`` with a
      non-null value. Empty ``non_null_fields`` is vacuous truth.
    - ``tool_succeeded``: every actual call's ``tool_result`` is a dict
      with ``isError`` absent or False. Catches protocol-level failures
      that vacuous-truth ``result_match`` would otherwise pass through.
    - ``completed``: copy of ``result.completed``.

    Mutates ``result.scores`` in place and returns the same dict for
    convenience at the call site.
    """
    actual = result.turns
    expected = case.expected_calls

    if len(actual) != len(expected):
        scores = {
            "tool_match": False,
            "args_match": False,
            "result_match": False,
            "tool_succeeded": False,
            "completed": result.completed,
        }
    else:
        tool_match = all(
            a.tool_name == e.tool for a, e in zip(actual, expected, strict=True)
        )
        args_match = all(
            _args_match(a.tool_args, e.args_subset)
            for a, e in zip(actual, expected, strict=True)
        )
        result_match = all(
            _result_match(a, e) for a, e in zip(actual, expected, strict=True)
        )
        tool_succeeded = all(_call_succeeded(a) for a in actual)
        scores = {
            "tool_match": tool_match,
            "args_match": args_match,
            "result_match": result_match,
            "tool_succeeded": tool_succeeded,
            "completed": result.completed,
        }

    result.scores = scores
    return scores
