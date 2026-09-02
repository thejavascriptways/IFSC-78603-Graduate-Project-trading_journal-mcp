from __future__ import annotations

from typing import Any

from app.providers.broker import BrokerProvider, BrokerProviderError


class BrokerServiceError(Exception):
    """Domain-level error for broker workflows."""


class BrokerService:
    """Coordinates broker connectivity and sync workflows."""

    def __init__(self, provider: BrokerProvider | None = None) -> None:
        self.provider = provider

    def get_status(self) -> dict[str, Any]:
        if self.provider is None:
            return {
                "configured": False,
                "provider": None,
                "mode": "not_configured",
                "notes": ["No broker provider is configured yet."],
            }
        return self.provider.get_status()

    def list_accounts(self) -> list[dict[str, Any]]:
        if self.provider is None:
            raise BrokerServiceError("No broker provider is configured yet.")
        try:
            return self.provider.list_accounts()
        except BrokerProviderError as exc:
            raise BrokerServiceError(str(exc)) from exc

    def list_positions(self, account_id: str) -> list[dict[str, Any]]:
        if self.provider is None:
            raise BrokerServiceError("No broker provider is configured yet.")
        try:
            return self.provider.list_positions(account_id)
        except BrokerProviderError as exc:
            raise BrokerServiceError(str(exc)) from exc

    def list_executions(self, account_id: str) -> list[dict[str, Any]]:
        if self.provider is None:
            raise BrokerServiceError("No broker provider is configured yet.")
        try:
            return self.provider.list_executions(account_id)
        except BrokerProviderError as exc:
            raise BrokerServiceError(str(exc)) from exc
