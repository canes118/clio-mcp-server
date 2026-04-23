"""Pure scoring logic over captured CaseResult data.

Kept separate from evals/harness.py so that tests and any other
consumer can import it without transitively pulling in the runtime
dependencies (anthropic, mcp) that the harness needs at live-run
time.
"""

from evals.cases import CaseResult, TestCase


def score(case: TestCase, result: CaseResult) -> dict[str, bool]:
    """Score a CaseResult against its TestCase expectations.

    Returns three booleans:

    - ``tool_match``: the first tool call matches ``case.expected_tool``.
    - ``args_match``: every ``(k, v)`` in ``case.expected_args_subset``
      is present in the first call's arguments with the expected value.
      Subset semantics — extra valid args in the actual call do not
      fail the check; a missing key or mismatched value does.
    - ``completed``: copy of ``result.completed``.

    If ``result.turns`` is empty, both ``tool_match`` and ``args_match``
    are False. Mutates ``result.scores`` in place and returns the same
    dict for convenience at the call site.
    """
    if not result.turns:
        tool_match = False
        args_match = False
    else:
        first = result.turns[0]
        tool_match = first.tool_name == case.expected_tool
        args_match = all(
            k in first.tool_args and first.tool_args[k] == v
            for k, v in case.expected_args_subset.items()
        )

    scores = {
        "tool_match": tool_match,
        "args_match": args_match,
        "completed": result.completed,
    }
    result.scores = scores
    return scores
