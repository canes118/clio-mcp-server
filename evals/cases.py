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


class TestCase(BaseModel):
    name: str
    query: str
    expected_tool: str
    expected_args_subset: dict[str, Any]


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
        expected_tool="search_matters",
        expected_args_subset={"query": "Acme"},
    ),
]
