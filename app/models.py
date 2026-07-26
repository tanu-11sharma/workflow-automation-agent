"""Pydantic data models for the workflow automation agent."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class StepStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepDefinition(BaseModel):
    """One node in a workflow template's dependency graph."""

    name: str
    tool: str
    args: Dict[str, Any] = {}
    depends_on: List[str] = []


class WorkflowTemplate(BaseModel):
    name: str
    description: str
    steps: List[StepDefinition]


class StepResult(BaseModel):
    name: str
    tool: str
    status: StepStatus
    attempts: int
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowResult(BaseModel):
    workflow: str
    goal_input: Dict[str, Any]
    status: StepStatus
    steps: List[StepResult]
