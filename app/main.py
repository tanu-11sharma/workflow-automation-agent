"""FastAPI app exposing the workflow automation agent over HTTP."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.executor import run_workflow
from app.models import WorkflowResult
from app.workflows import WORKFLOW_REGISTRY

app = FastAPI(
    title="Workflow Automation Agent",
    description=(
        "Demo agent that chains multiple mock tool calls together to complete "
        "a multi-step goal (e.g. customer onboarding). All tools are in-memory "
        "simulations -- no real account, email, calendar, or CRM system is touched."
    ),
    version="0.1.0",
)


class OnboardingRequest(BaseModel):
    name: str = "Jordan Rivera"
    email: str = "jordan.rivera@example.com"
    plan: str = "pro"
    kickoff_when: str = "next business day"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/workflows")
def list_workflows() -> list[dict]:
    """List the available workflow templates and their step graphs."""
    return [
        {
            "name": wf.name,
            "description": wf.description,
            "steps": [
                {"name": s.name, "tool": s.tool, "depends_on": s.depends_on}
                for s in wf.steps
            ],
        }
        for wf in WORKFLOW_REGISTRY.values()
    ]


@app.post("/workflows/{workflow_name}/run", response_model=WorkflowResult)
def run_named_workflow(workflow_name: str, request: OnboardingRequest = OnboardingRequest()) -> WorkflowResult:
    """Run a named workflow (e.g. 'customer_onboarding') end to end and return the execution report."""
    template = WORKFLOW_REGISTRY.get(workflow_name)
    if template is None:
        raise HTTPException(status_code=404, detail=f"No workflow named '{workflow_name}'")
    return run_workflow(template, request.model_dump())
