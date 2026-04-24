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
) -> TestCase:
    return TestCase(
        name="t",
        query="q",
        expected_tool=expected_tool,
        expected_args_subset=subset or {},
    )


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
