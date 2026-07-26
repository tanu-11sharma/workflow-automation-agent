"""Workflow templates: declarative step graphs the executor runs."""
from app.models import StepDefinition, WorkflowTemplate

CUSTOMER_ONBOARDING = WorkflowTemplate(
    name="customer_onboarding",
    description=(
        "Onboard a new customer end to end: create their account, provision a "
        "workspace, send a welcome email, schedule a kickoff call, and log them "
        "in the CRM. All five steps run against in-memory mock tools -- no real "
        "account, email, calendar, or CRM system is touched."
    ),
    steps=[
        StepDefinition(
            name="create_account",
            tool="create_account",
            args={"name": "{input.name}", "email": "{input.email}"},
            depends_on=[],
        ),
        StepDefinition(
            name="provision_workspace",
            tool="provision_workspace",
            args={"account_id": "{create_account.account_id}", "plan": "{input.plan}"},
            depends_on=["create_account"],
        ),
        StepDefinition(
            name="send_welcome_email",
            tool="send_welcome_email",
            args={"account_id": "{create_account.account_id}"},
            depends_on=["create_account"],
        ),
        StepDefinition(
            name="schedule_kickoff_call",
            tool="schedule_kickoff_call",
            args={
                "workspace_id": "{provision_workspace.workspace_id}",
                "when": "{input.kickoff_when}",
            },
            depends_on=["provision_workspace"],
        ),
        StepDefinition(
            name="add_to_crm",
            tool="add_to_crm",
            args={"account_id": "{create_account.account_id}"},
            depends_on=["create_account"],
        ),
    ],
)

WORKFLOW_REGISTRY = {
    CUSTOMER_ONBOARDING.name: CUSTOMER_ONBOARDING,
}
