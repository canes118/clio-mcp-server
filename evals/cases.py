"""Eval case and result models.

Data shapes the harness consumes: a `TestCase` describes a committed
eval scenario, a `TurnRecord` captures one tool call within the agent
loop, and a `CaseResult` collects the full run output for later scoring
and persistence. Tool results are kept at full fidelity here;
confidentiality is enforced by gitignoring `evals/runs/`, not by
redacting at capture time.

This file is committed to a public repository. Every query, name, and
expected arg in `CASES` must use generic placeholders per CLAUDE.md
(e.g. "Acme", "Widget Corp", "Example LLC"). Never a real firm or
client name.
"""

from typing import Any

from pydantic import BaseModel, Field


class TurnRecord(BaseModel):
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: Any
    latency_ms: float


class ExpectedCall(BaseModel):
    tool: str
    args_subset: dict[str, Any] = Field(default_factory=dict)
    non_null_fields: list[str] = Field(default_factory=list)


class TestCase(BaseModel):
    __test__ = False  # not a pytest test class; name collides with the heuristic

    name: str
    query: str
    expected_calls: list[ExpectedCall]


class CaseResult(BaseModel):
    case_name: str
    prompt: str
    turns: list[TurnRecord]
    final_text: str
    scores: dict[str, bool] = Field(default_factory=dict)
    iterations: int
    wall_time_ms: float
    completed: bool


CASES: list[TestCase] = [
    TestCase(
        name="search_matters_generic_term",
        query="find the Acme matter",
        expected_calls=[
            ExpectedCall(
                tool="search_matters",
                args_subset={"query": "Acme"},
            ),
        ],
    ),
    TestCase(
        name="search_contacts_company",
        query="find the Acme company in my contacts",
        expected_calls=[
            ExpectedCall(
                tool="search_contacts",
                args_subset={"query": "Acme", "type": "Company"},
            ),
        ],
    ),
    TestCase(
        name="get_matter_by_id",
        query="Give me details on matter 1668402907",
        expected_calls=[
            ExpectedCall(
                tool="get_matter",
                args_subset={"matter_id": 1668402907},
                non_null_fields=["description", "status"],
            ),
        ],
    ),
    TestCase(
        name="get_contact_by_id",
        query="Give me details on contact 1809175816",
        expected_calls=[
            ExpectedCall(
                tool="get_contact",
                args_subset={"contact_id": 1809175816},
                non_null_fields=[
                    "first_name",
                    "last_name",
                    "primary_email_address",
                ],
            ),
        ],
    ),
    TestCase(
        name="search_matters_status_filter",
        query="What open matters do I have?",
        expected_calls=[
            ExpectedCall(
                tool="search_matters",
                args_subset={"status": "open"},
            ),
        ],
    ),
    TestCase(
        name="matter_to_client_drilldown",
        query="What's the full contact info for the client on matter id 1668402907?",
        expected_calls=[
            ExpectedCall(
                tool="get_matter",
                args_subset={"matter_id": 1668402907},
                non_null_fields=["description", "status"],
            ),
            ExpectedCall(
                tool="get_contact",
                args_subset={"contact_id": 2168806432},
                non_null_fields=["type", "name"],
            ),
        ],
    ),
]
