from __future__ import annotations

from typing import Any

from app.providers.broker.base import BrokerProviderError


class IBKRBrokerProvider:
    """Placeholder adapter for the planned Interactive Brokers integration."""

    name = "ibkr"

    def get_status(self) -> dict[str, Any]:
        return {
            "configured": False,
            "provider": self.name,
            "mode": "not_configured",
            "notes": ["IBKR broker integration is planned but not implemented yet."],
        }

    def list_accounts(self) -> list[dict[str, Any]]:
        raise BrokerProviderError("IBKR account discovery is not implemented yet.")

    def list_positions(self, account_id: str) -> list[dict[str, Any]]:
        raise BrokerProviderError(f"IBKR position sync is not implemented yet for account '{account_id}'.")

    def list_executions(self, account_id: str) -> list[dict[str, Any]]:
        raise BrokerProviderError(f"IBKR execution sync is not implemented yet for account '{account_id}'.")
