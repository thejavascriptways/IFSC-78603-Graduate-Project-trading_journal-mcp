from __future__ import annotations

from typing import Any, Protocol


class BrokerProviderError(Exception):
    """Raised when a broker provider call fails."""


class BrokerProvider(Protocol):
    """Contract implemented by broker adapters such as IBKR."""

    name: str

    def get_status(self) -> dict[str, Any]:
        """Return authentication/session status for the broker connection."""

    def list_accounts(self) -> list[dict[str, Any]]:
        """Return broker accounts available to the authenticated user."""

    def list_positions(self, account_id: str) -> list[dict[str, Any]]:
        """Return broker positions for an account."""

    def list_executions(self, account_id: str) -> list[dict[str, Any]]:
        """Return recent broker executions for an account."""
