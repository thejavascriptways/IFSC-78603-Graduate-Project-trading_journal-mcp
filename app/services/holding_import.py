from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Account
from app.models.enums import AccountSource, AssetClass
from app.schemas import OpeningHoldingCreate
from app.services.portfolio import PortfolioError, import_opening_holding


OPENING_HOLDING_CSV_FIELDS = [
    "account_name",
    "symbol",
    "description",
    "asset_class",
    "opening_date",
    "quantity",
    "average_cost",
    "currency",
    "notes",
]

OPENING_HOLDING_SAMPLE_CSV = (
    ",".join(OPENING_HOLDING_CSV_FIELDS)
    + "\n"
    + "Manual Fidelity,VOO,Vanguard S&P 500 ETF,ETF,2026-01-02,10,500.25,USD,Initial Fidelity import\n"
    + "Manual Fidelity,AAPL,Apple Inc.,STOCK,2026-02-15,5,180.10,USD,Long-term core position\n"
)


@dataclass(frozen=True)
class BulkOpeningHoldingImportResult:
    imported_count: int
    failed_count: int
    row_errors: list[str]

    @property
    def total_rows(self) -> int:
        return self.imported_count + self.failed_count


class HoldingImportCsvError(Exception):
    """Raised when a CSV file cannot be parsed for bulk holding import."""


def import_opening_holdings_from_csv(session: Session, csv_bytes: bytes) -> BulkOpeningHoldingImportResult:
    text = _decode_csv(csv_bytes)
    reader = csv.DictReader(StringIO(text))

    if reader.fieldnames is None:
        raise HoldingImportCsvError("CSV file is empty or does not include a header row.")

    missing_fields = [field for field in OPENING_HOLDING_CSV_FIELDS if field not in reader.fieldnames]
    if missing_fields:
        raise HoldingImportCsvError("CSV is missing required columns: " + ", ".join(missing_fields) + ".")

    imported_count = 0
    row_errors: list[str] = []

    for row_number, row in enumerate(reader, start=2):
        if _is_blank_row(row):
            continue

        try:
            payload = _payload_from_csv_row(session, row)
            import_opening_holding(session, payload)
            imported_count += 1
        except (PortfolioError, ValidationError, ValueError, InvalidOperation) as exc:
            session.rollback()
            symbol = (row.get("symbol") or "unknown symbol").strip() or "unknown symbol"
            row_errors.append(f"Row {row_number} ({symbol}): {exc}")

    return BulkOpeningHoldingImportResult(
        imported_count=imported_count,
        failed_count=len(row_errors),
        row_errors=row_errors,
    )


def _decode_csv(csv_bytes: bytes) -> str:
    if not csv_bytes:
        raise HoldingImportCsvError("CSV file is empty.")
    try:
        return csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HoldingImportCsvError("CSV file must be UTF-8 encoded.") from exc


def _payload_from_csv_row(session: Session, row: dict[str, str | None]) -> OpeningHoldingCreate:
    account_name = _required_text(row, "account_name")
    account = session.scalar(
        select(Account).where(
            Account.name == account_name,
            Account.source == AccountSource.MANUAL,
            Account.is_active.is_(True),
        )
    )
    if account is None:
        raise PortfolioError(f"Manual account '{account_name}' does not exist.")

    return OpeningHoldingCreate(
        account_id=account.id,
        symbol=_required_text(row, "symbol"),
        description=_optional_text(row, "description"),
        asset_class=AssetClass(_required_text(row, "asset_class").upper()),
        opening_date=date.fromisoformat(_required_text(row, "opening_date")),
        quantity=Decimal(_required_text(row, "quantity")),
        average_cost=Decimal(_required_text(row, "average_cost")),
        currency=_optional_text(row, "currency") or "USD",
        notes=_optional_text(row, "notes"),
    )


def _required_text(row: dict[str, str | None], field_name: str) -> str:
    value = _optional_text(row, field_name)
    if value is None:
        raise ValueError(f"{field_name} is required.")
    return value


def _optional_text(row: dict[str, str | None], field_name: str) -> str | None:
    value = row.get(field_name)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _is_blank_row(row: dict[str, str | None]) -> bool:
    return all((value or "").strip() == "" for value in row.values())
