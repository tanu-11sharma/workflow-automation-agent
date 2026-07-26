"""
Mock tools the workflow agent chains together.

Every tool here is a pure, in-memory simulation -- there is no real account
system, email provider, calendar, or CRM behind these calls. Each call is
logged to an in-memory store so a run's side effects can be inspected, and
one tool (`send_welcome_email`) is deliberately flaky the first time it is
called per run, to exercise the executor's retry path deterministically.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict


class MockSystemState:
    """In-memory stand-in for the external systems a real agent would call."""

    def __init__(self) -> None:
        self._id_counter = itertools.count(1)
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.workspaces: Dict[str, Dict[str, Any]] = {}
        self.emails_sent: Dict[str, Dict[str, Any]] = {}
        self.events: Dict[str, Dict[str, Any]] = {}
        self.crm_records: Dict[str, Dict[str, Any]] = {}
        self._email_attempts: Dict[str, int] = {}

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._id_counter):04d}"

    def create_account(self, name: str, email: str) -> Dict[str, Any]:
        account_id = self._next_id("acct")
        self.accounts[account_id] = {"name": name, "email": email}
        return {"account_id": account_id}

    def provision_workspace(self, account_id: str, plan: str = "standard") -> Dict[str, Any]:
        if account_id not in self.accounts:
            raise ValueError(f"unknown account_id: {account_id}")
        workspace_id = self._next_id("ws")
        self.workspaces[workspace_id] = {"account_id": account_id, "plan": plan}
        return {"workspace_id": workspace_id}

    def send_welcome_email(self, account_id: str) -> Dict[str, Any]:
        """Fails on the first attempt per account, succeeds on retry.

        This simulates a transient provider error (e.g. a rate limit) so the
        executor's retry-once policy has something real to demonstrate.
        """
        if account_id not in self.accounts:
            raise ValueError(f"unknown account_id: {account_id}")
        attempts = self._email_attempts.get(account_id, 0) + 1
        self._email_attempts[account_id] = attempts
        if attempts == 1:
            raise RuntimeError("simulated transient email provider error (rate limited)")
        message_id = self._next_id("msg")
        self.emails_sent[message_id] = {"account_id": account_id}
        return {"message_id": message_id}

    def schedule_kickoff_call(self, workspace_id: str, when: str = "next business day") -> Dict[str, Any]:
        if workspace_id not in self.workspaces:
            raise ValueError(f"unknown workspace_id: {workspace_id}")
        event_id = self._next_id("evt")
        self.events[event_id] = {"workspace_id": workspace_id, "when": when}
        return {"event_id": event_id}

    def add_to_crm(self, account_id: str) -> Dict[str, Any]:
        if account_id not in self.accounts:
            raise ValueError(f"unknown account_id: {account_id}")
        crm_id = self._next_id("crm")
        self.crm_records[crm_id] = {"account_id": account_id}
        return {"crm_id": crm_id}


TOOL_REGISTRY = {
    "create_account": MockSystemState.create_account,
    "provision_workspace": MockSystemState.provision_workspace,
    "send_welcome_email": MockSystemState.send_welcome_email,
    "schedule_kickoff_call": MockSystemState.schedule_kickoff_call,
    "add_to_crm": MockSystemState.add_to_crm,
}
