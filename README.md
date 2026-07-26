# Workflow Automation Agent

A small agent that takes a high-level goal ("onboard this customer") and
chains together five mock tool calls in dependency order to get it done:
create the account, provision a workspace, send a welcome email, schedule a
kickoff call, and log the account in the CRM -- then returns a structured
report of exactly what ran, in what order, and with how many attempts.

**This is a demo/simulation.** Every "tool" (account system, email, calendar,
CRM) is an in-memory mock defined in `app/tools.py`. No real account is
created, no real email is sent, and no real external system is touched.

## Why this pattern

Workflow/task-automation agents are one of the most common agentic shapes in
production right now: given a goal, decompose it into a sequence of tool
calls with dependencies between them, execute in the right order, retry
transient failures, and hand back an auditable trace. Here the "plan" is a
declarative `WorkflowTemplate` (a small step graph with `depends_on` edges)
rather than something an LLM improvises at runtime, which makes the whole
thing deterministic and easy to unit test -- a solid skeleton to later let a
model choose or generate the plan while keeping the same execution engine.

## What's inside

- `app/tools.py` -- five mock tools (`create_account`, `provision_workspace`,
  `send_welcome_email`, `schedule_kickoff_call`, `add_to_crm`) backed by an
  in-memory `MockSystemState`. `send_welcome_email` deliberately fails on its
  first call per run (simulated rate limit) so the retry path has something
  real to demonstrate.
- `app/workflows.py` -- the `customer_onboarding` workflow template: a
  5-step dependency graph (not just a flat list -- `schedule_kickoff_call`
  and `add_to_crm` both branch off different upstream steps).
- `app/executor.py` -- the agent: topologically sorts the steps, resolves
  each step's arguments from the goal input and prior steps' outputs
  (`"{create_account.account_id}"`-style placeholders), calls the tool,
  retries once on failure, and skips any step whose dependency failed.
- `app/main.py` -- a small FastAPI service to run workflows over HTTP.
- `tests/test_executor.py` -- covers full success, dependency ordering, the
  retry-then-succeed path, skip-on-upstream-failure, and cycle/unknown-
  dependency rejection.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Then in another terminal:

```bash
# List available workflow templates and their step graphs
curl http://127.0.0.1:8000/workflows

# Run the customer-onboarding workflow with default sample input
curl -X POST http://127.0.0.1:8000/workflows/customer_onboarding/run

# Run it with your own input
curl -X POST http://127.0.0.1:8000/workflows/customer_onboarding/run \
  -H "Content-Type: application/json" \
  -d '{"name": "Alex Chen", "email": "alex@example.com", "plan": "team", "kickoff_when": "this Friday"}'
```

Or run it without a server, straight from Python:

```bash
python -c "
from app.executor import run_workflow
from app.workflows import CUSTOMER_ONBOARDING
result = run_workflow(CUSTOMER_ONBOARDING, {
    'name': 'Jordan Rivera', 'email': 'jordan.rivera@example.com',
    'plan': 'pro', 'kickoff_when': 'next business day',
})
for step in result.steps:
    print(f'{step.status.value:10} attempts={step.attempts}  {step.name}')
print('overall:', result.status.value)
"
```

## Test

```bash
pytest -v
```

## Docker (optional)

```bash
docker build -t workflow-automation-agent .
docker run -p 8000:8000 workflow-automation-agent
```

## Disclaimer

Sample/synthetic data only. This project does not create real accounts,
send real email, book real calendar events, or write to any real CRM.
