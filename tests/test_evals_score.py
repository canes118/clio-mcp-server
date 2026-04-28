"""Unit tests for evals.harness.score.

score() is the one piece of interpretation logic in the harness; the
subset-match semantics on expected_args_subset are easy to break
accidentally during a later "simplify" pass, so they are pinned here.
"""

from typing import Any

from evals.cases import CaseResult, TestCase, TurnRecord
from evals.scoring import score


def _case(
    expected_tool: str = "search_matters",
    subset: dict[str, Any] | None = None,
    non_null_fields: list[str] | None = None,
) -> TestCase:
    return TestCase(
        name="t",
        query="q",
        expected_tool=expected_tool,
        expected_args_subset=subset or {},
        expected_non_null_fields=non_null_fields or [],
    )


def _dict_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Mimic an MCP CallToolResult dump whose tool returned a dict-shaped model."""
    return {
        "meta": None,
        "content": [{"type": "text", "text": "{}"}],
        "structuredContent": payload,
        "isError": False,
    }


def _list_payload(items: list[Any]) -> dict[str, Any]:
    """Mimic an MCP CallToolResult dump whose tool returned a list (FastMCP wraps it)."""
    return {
        "meta": {"fastmcp": {"wrap_result": True}},
        "content": [{"type": "text", "text": "[]"}],
        "structuredContent": {"result": items},
        "isError": False,
    }


_UNSET: Any = object()


def _turn(
    name: str = "search_matters",
    args: dict[str, Any] | None = None,
    tool_result: Any = _UNSET,
) -> TurnRecord:
    if tool_result is _UNSET:
        tool_result = {"isError": False, "content": []}
    return TurnRecord(
        tool_name=name,
        tool_args=args or {},
        tool_result=tool_result,
        latency_ms=0.0,
    )


def _result(
    turns: list[TurnRecord] | None = None,
    completed: bool = True,
) -> CaseResult:
    return CaseResult(
        case_name="t",
        prompt="q",
        turns=turns or [],
        final_text="",
        iterations=1,
        wall_time_ms=0.0,
        completed=completed,
    )


def test_empty_turns_yields_all_false() -> None:
    case = _case(subset={"query": "Acme"})
    result = _result(turns=[], completed=False)

    scores = score(case, result)

    assert scores == {
        "tool_match": False,
        "args_match": False,
        "result_match": False,
        "tool_succeeded": False,
        "completed": False,
    }
    assert result.scores == scores


def test_correct_tool_and_exact_args_passes() -> None:
    case = _case(expected_tool="search_matters", subset={"query": "Acme"})
    result = _result(turns=[_turn(name="search_matters", args={"query": "Acme"})])

    scores = score(case, result)

    assert scores["tool_match"] is True
    assert scores["args_match"] is True
    assert scores["completed"] is True


def test_superset_of_expected_args_still_matches() -> None:
    case = _case(subset={"query": "Acme"})
    result = _result(
        turns=[_turn(args={"query": "Acme", "limit": 10, "status": "Open"})]
    )

    scores = score(case, result)

    assert scores["args_match"] is True


def test_missing_expected_key_fails_args_match() -> None:
    case = _case(subset={"query": "Acme"})
    result = _result(turns=[_turn(args={"limit": 10})])

    scores = score(case, result)

    assert scores["tool_match"] is True
    assert scores["args_match"] is False


def test_mismatched_value_for_expected_key_fails_args_match() -> None:
    case = _case(subset={"query": "Acme"})
    result = _result(turns=[_turn(args={"query": "Widget"})])

    scores = score(case, result)

    assert scores["args_match"] is False


def test_wrong_tool_fails_tool_match() -> None:
    case = _case(expected_tool="search_matters", subset={"query": "Acme"})
    result = _result(turns=[_turn(name="search_contacts", args={"query": "Acme"})])

    scores = score(case, result)

    assert scores["tool_match"] is False


def test_completed_reflects_result_completed() -> None:
    case = _case()
    result = _result(turns=[_turn()], completed=False)

    scores = score(case, result)

    assert scores["completed"] is False


def test_score_mutates_result_scores_in_place() -> None:
    case = _case()
    result = _result(turns=[_turn()])

    returned = score(case, result)

    assert result.scores == returned
    assert result.scores is returned


def test_empty_expected_subset_matches_any_args() -> None:
    case = _case(expected_tool="search_matters", subset={})
    result = _result(turns=[_turn(args={"query": "Acme"})])

    scores = score(case, result)

    assert scores["args_match"] is True


def test_tool_succeeded_true_when_first_turn_not_errored() -> None:
    case = _case()
    result = _result(turns=[_turn(tool_result={"isError": False, "content": []})])

    scores = score(case, result)

    assert scores["tool_succeeded"] is True


def test_tool_succeeded_false_when_first_turn_errored() -> None:
    case = _case()
    result = _result(turns=[_turn(tool_result={"isError": True, "content": []})])

    scores = score(case, result)

    assert scores["tool_succeeded"] is False


def test_tool_succeeded_false_when_is_error_key_missing() -> None:
    case = _case()
    result = _result(turns=[_turn(tool_result={"content": []})])

    scores = score(case, result)

    assert scores["tool_succeeded"] is False


def test_tool_succeeded_false_when_tool_result_is_not_a_dict() -> None:
    case = _case()
    result = _result(turns=[_turn(tool_result=None)])

    scores = score(case, result)

    assert scores["tool_succeeded"] is False

    result = _result(turns=[_turn(tool_result="some string")])

    scores = score(case, result)

    assert scores["tool_succeeded"] is False


def test_tool_succeeded_only_considers_first_turn() -> None:
    case = _case()
    result = _result(
        turns=[
            _turn(tool_result={"isError": True, "content": []}),
            _turn(tool_result={"isError": False, "content": []}),
        ],
    )

    scores = score(case, result)

    assert scores["tool_succeeded"] is False


def test_result_match_passes_when_all_listed_fields_non_null() -> None:
    case = _case(
        expected_tool="get_matter",
        non_null_fields=["description", "status"],
    )
    result = _result(
        turns=[
            _turn(
                name="get_matter",
                tool_result=_dict_payload(
                    {"id": 1, "description": "Acme Lend", "status": "Open"}
                ),
            )
        ]
    )

    scores = score(case, result)

    assert scores["result_match"] is True


def test_result_match_fails_when_listed_field_is_null() -> None:
    case = _case(
        expected_tool="get_matter",
        non_null_fields=["description", "status"],
    )
    result = _result(
        turns=[
            _turn(
                name="get_matter",
                tool_result=_dict_payload(
                    {"id": 1, "description": None, "status": "Open"}
                ),
            )
        ]
    )

    scores = score(case, result)

    assert scores["result_match"] is False


def test_result_match_fails_when_listed_field_is_absent() -> None:
    case = _case(
        expected_tool="get_matter",
        non_null_fields=["description", "status"],
    )
    result = _result(
        turns=[
            _turn(
                name="get_matter",
                tool_result=_dict_payload({"id": 1, "status": "Open"}),
            )
        ]
    )

    scores = score(case, result)

    assert scores["result_match"] is False


def test_result_match_vacuous_with_empty_expected_fields() -> None:
    case = _case(expected_tool="search_matters", non_null_fields=[])
    result = _result(
        turns=[
            _turn(
                name="search_matters",
                tool_result=_list_payload([{"id": 1}]),
            )
        ]
    )

    scores = score(case, result)

    assert scores["result_match"] is True


def test_result_match_fails_for_list_payload_with_non_empty_expected() -> None:
    # Misconfigured: list-shape result paired with field-level expectations.
    case = _case(
        expected_tool="search_matters",
        non_null_fields=["description"],
    )
    result = _result(
        turns=[
            _turn(
                name="search_matters",
                tool_result=_list_payload([{"description": "Acme"}]),
            )
        ]
    )

    scores = score(case, result)

    assert scores["result_match"] is False


def test_result_match_fails_when_expected_tool_was_not_called() -> None:
    case = _case(
        expected_tool="get_matter",
        non_null_fields=["description"],
    )
    result = _result(
        turns=[
            _turn(
                name="search_matters",
                tool_result=_list_payload([{"description": "Acme"}]),
            )
        ]
    )

    scores = score(case, result)

    assert scores["result_match"] is False


def test_result_match_unwraps_fastmcp_wrapped_dict() -> None:
    # Discriminated unions (e.g. Contact) come back wrapped as {"result": <dict>}.
    case = _case(
        expected_tool="get_contact",
        non_null_fields=["first_name", "last_name"],
    )
    wrapped = {
        "meta": {"fastmcp": {"wrap_result": True}},
        "content": [{"type": "text", "text": "{}"}],
        "structuredContent": {
            "result": {"first_name": "Jane", "last_name": "Smith"}
        },
        "isError": False,
    }
    result = _result(
        turns=[_turn(name="get_contact", tool_result=wrapped)]
    )

    scores = score(case, result)

    assert scores["result_match"] is True
