import pytest

from app.executor import run_workflow, _topological_order
from app.models import StepDefinition, StepStatus, WorkflowTemplate
from app.workflows import CUSTOMER_ONBOARDING


GOAL_INPUT = {
    "name": "Jordan Rivera",
    "email": "jordan.rivera@example.com",
    "plan": "pro",
    "kickoff_when": "next business day",
}


def test_full_onboarding_workflow_succeeds_all_five_steps():
    result = run_workflow(CUSTOMER_ONBOARDING, GOAL_INPUT)
    assert result.status == StepStatus.SUCCEEDED
    assert len(result.steps) == 5
    assert all(s.status == StepStatus.SUCCEEDED for s in result.steps)


def test_create_account_runs_before_its_dependents():
    result = run_workflow(CUSTOMER_ONBOARDING, GOAL_INPUT)
    order = [s.name for s in result.steps]
    idx_create = order.index("create_account")
    for dependent in ("provision_workspace", "send_welcome_email", "add_to_crm"):
        assert order.index(dependent) > idx_create
    assert order.index("schedule_kickoff_call") > order.index("provision_workspace")


def test_flaky_welcome_email_succeeds_on_retry():
    result = run_workflow(CUSTOMER_ONBOARDING, GOAL_INPUT)
    email_step = next(s for s in result.steps if s.name == "send_welcome_email")
    assert email_step.status == StepStatus.SUCCEEDED
    assert email_step.attempts == 2  # fails once (simulated), succeeds on retry


def test_outputs_are_threaded_between_steps():
    result = run_workflow(CUSTOMER_ONBOARDING, GOAL_INPUT)
    account_id = next(s for s in result.steps if s.name == "create_account").output["account_id"]
    workspace_step = next(s for s in result.steps if s.name == "provision_workspace")
    # provision_workspace doesn't echo account_id back, but it must have succeeded
    # using the account_id produced by create_account (enforced inside the tool).
    assert workspace_step.status == StepStatus.SUCCEEDED
    assert account_id.startswith("acct_")


def test_dependent_step_is_skipped_when_its_dependency_fails():
    steps = [
        StepDefinition(name="create_account", tool="create_account",
                       args={"name": "{input.name}", "email": "{input.email}"}, depends_on=[]),
        StepDefinition(name="provision_workspace", tool="provision_workspace",
                       args={"account_id": "acct_does_not_exist", "plan": "{input.plan}"},
                       depends_on=["create_account"]),
        StepDefinition(name="schedule_kickoff_call", tool="schedule_kickoff_call",
                       args={"workspace_id": "{provision_workspace.workspace_id}", "when": "later"},
                       depends_on=["provision_workspace"]),
    ]
    template = WorkflowTemplate(name="broken", description="forces a failure", steps=steps)
    result = run_workflow(template, GOAL_INPUT)

    assert result.status == StepStatus.FAILED
    by_name = {s.name: s for s in result.steps}
    assert by_name["create_account"].status == StepStatus.SUCCEEDED
    assert by_name["provision_workspace"].status == StepStatus.FAILED
    assert by_name["schedule_kickoff_call"].status == StepStatus.SKIPPED


def test_cycle_in_workflow_graph_is_rejected():
    steps = [
        StepDefinition(name="a", tool="create_account", args={}, depends_on=["b"]),
        StepDefinition(name="b", tool="create_account", args={}, depends_on=["a"]),
    ]
    with pytest.raises(ValueError):
        _topological_order(steps)


def test_unknown_dependency_is_rejected():
    steps = [
        StepDefinition(name="a", tool="create_account", args={}, depends_on=["ghost"]),
    ]
    with pytest.raises(ValueError):
        _topological_order(steps)
