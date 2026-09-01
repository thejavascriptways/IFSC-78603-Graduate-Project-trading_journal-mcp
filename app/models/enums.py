from __future__ import annotations

from enum import StrEnum


class AccountSource(StrEnum):
    IBKR = "IBKR"
    MANUAL = "MANUAL"


class AssetClass(StrEnum):
    STOCK = "STOCK"
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    BOND = "BOND"
    OPTION = "OPTION"
    CASH = "CASH"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TradeOrigin(StrEnum):
    OPENING = "OPENING"
    MANUAL = "MANUAL"
    IMPORTED = "IMPORTED"
