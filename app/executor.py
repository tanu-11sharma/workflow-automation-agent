"""
Workflow executor: the agent that chains tool calls together.

Given a WorkflowTemplate (a small dependency graph of steps) and a goal
input, this walks the steps in dependency order, resolves each step's
arguments from the original input and prior steps' outputs, calls the
corresponding mock tool, retries once on failure, and returns a structured
report of what happened -- the same "plan -> call tools in order -> report"
loop behind most workflow/task-automation agents, just without an LLM
choosing the plan (the plan is the declarative WorkflowTemplate).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.models import StepDefinition, StepResult, StepStatus, WorkflowResult, WorkflowTemplate
from app.tools import TOOL_REGISTRY, MockSystemState

_PLACEHOLDER = re.compile(r"^\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\}$")

MAX_ATTEMPTS = 2  # one real attempt + one retry


def _topological_order(steps: List[StepDefinition]) -> List[StepDefinition]:
    by_name = {s.name: s for s in steps}
    visited: Dict[str, int] = {}  # 0 = in progress, 1 = done
    order: List[StepDefinition] = []

    def visit(name: str) -> None:
        state = visited.get(name)
        if state == 1:
            return
        if state == 0:
            raise ValueError(f"cycle detected in workflow at step '{name}'")
        visited[name] = 0
        for dep in by_name[name].depends_on:
            if dep not in by_name:
                raise ValueError(f"step '{name}' depends on unknown step '{dep}'")
            visit(dep)
        visited[name] = 1
        order.append(by_name[name])

    for step in steps:
        visit(step.name)
    return order


def _resolve_value(value: Any, goal_input: Dict[str, Any], outputs: Dict[str, Dict[str, Any]]) -> Any:
    if not isinstance(value, str):
        return value
    match = _PLACEHOLDER.match(value)
    if not match:
        return value
    source, key = match.group(1), match.group(2)
    if source == "input":
        return goal_input[key]
    if source not in outputs:
        raise KeyError(f"no output available yet from step '{source}'")
    return outputs[source][key]


def run_workflow(template: WorkflowTemplate, goal_input: Dict[str, Any]) -> WorkflowResult:
    order = _topological_order(template.steps)
    system = MockSystemState()
    outputs: Dict[str, Dict[str, Any]] = {}
    results: List[StepResult] = []
    failed_steps: set[str] = set()

    for step in order:
        if any(dep in failed_steps for dep in step.depends_on):
            results.append(
                StepResult(name=step.name, tool=step.tool, status=StepStatus.SKIPPED, attempts=0)
            )
            failed_steps.add(step.name)
            continue

        tool_fn = TOOL_REGISTRY[step.tool]
        attempts = 0
        last_error: str | None = None
        succeeded = False
        output: Dict[str, Any] | None = None

        while attempts < MAX_ATTEMPTS and not succeeded:
            attempts += 1
            try:
                resolved_args = {
                    k: _resolve_value(v, goal_input, outputs) for k, v in step.args.items()
                }
                output = tool_fn(system, **resolved_args)
                succeeded = True
            except Exception as exc:  # noqa: BLE001 -- deliberately broad: any tool can fail
                last_error = str(exc)

        if succeeded:
            outputs[step.name] = output or {}
            results.append(
                StepResult(
                    name=step.name,
                    tool=step.tool,
                    status=StepStatus.SUCCEEDED,
                    attempts=attempts,
                    output=output,
                )
            )
        else:
            failed_steps.add(step.name)
            results.append(
                StepResult(
                    name=step.name,
                    tool=step.tool,
                    status=StepStatus.FAILED,
                    attempts=attempts,
                    error=last_error,
                )
            )

    overall_status = (
        StepStatus.SUCCEEDED
        if all(r.status == StepStatus.SUCCEEDED for r in results)
        else StepStatus.FAILED
    )

    return WorkflowResult(
        workflow=template.name,
        goal_input=goal_input,
        status=overall_status,
        steps=results,
    )
