"""Pure scoring logic over captured CaseResult data.

Kept separate from evals/harness.py so that tests and any other
consumer can import it without transitively pulling in the runtime
dependencies (anthropic, mcp) that the harness needs at live-run
time.
"""

from typing import Any

from evals.cases import CaseResult, TestCase, TurnRecord


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


def _result_match(case: TestCase, turns: list[TurnRecord]) -> bool:
    matching = next((t for t in turns if t.tool_name == case.expected_tool), None)
    if matching is None:
        return False
    if not case.expected_non_null_fields:
        return True
    payload = _extract_payload(matching.tool_result)
    # List-shape checks are deliberately out of scope for v1: a non-empty
    # expected_non_null_fields against a list result means the case was
    # configured for a get-by-id-style tool but pointed at a search tool.
    if isinstance(payload, list):
        return False
    if not isinstance(payload, dict):
        return False
    return all(
        field in payload and payload[field] is not None
        for field in case.expected_non_null_fields
    )


def score(case: TestCase, result: CaseResult) -> dict[str, bool]:
    """Score a CaseResult against its TestCase expectations.

    Returns five booleans:

    - ``tool_match``: the first tool call matches ``case.expected_tool``.
    - ``args_match``: every ``(k, v)`` in ``case.expected_args_subset``
      is present in the first call's arguments with the expected value.
      Subset semantics — extra valid args in the actual call do not
      fail the check; a missing key or mismatched value does.
    - ``result_match``: the first turn whose ``tool_name`` matches
      ``case.expected_tool`` returned a dict containing every field in
      ``case.expected_non_null_fields`` with a non-null value. Missing
      keys are treated as null. Empty ``expected_non_null_fields`` is
      vacuous truth (matches the args-subset semantics). False when
      the expected tool was not called.
    - ``tool_succeeded``: the first turn's ``tool_result`` is a dict
      with ``isError`` set to False. Absent ``isError`` or a non-dict
      result is treated as failure, not silent success.
    - ``completed``: copy of ``result.completed``.

    If ``result.turns`` is empty, ``tool_match``, ``args_match``,
    ``result_match``, and ``tool_succeeded`` are all False. Mutates
    ``result.scores`` in place and returns the same dict for
    convenience at the call site.
    """
    if not result.turns:
        tool_match = False
        args_match = False
        tool_succeeded = False
    else:
        first = result.turns[0]
        tool_match = first.tool_name == case.expected_tool
        args_match = all(
            k in first.tool_args and first.tool_args[k] == v
            for k, v in case.expected_args_subset.items()
        )
        tool_result = first.tool_result
        if isinstance(tool_result, dict):
            tool_succeeded = not tool_result.get("isError", True)
        else:
            tool_succeeded = False

    scores = {
        "tool_match": tool_match,
        "args_match": args_match,
        "result_match": _result_match(case, result.turns),
        "tool_succeeded": tool_succeeded,
        "completed": result.completed,
    }
    result.scores = scores
    return scores
