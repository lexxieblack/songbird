from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from songbird.models.exception import SongbirdException


class CurrencyError(SongbirdException):
    """Raised when a currency conversion cannot be completed."""


class Currency(BaseModel):
    iso_code: str
    name: str
    symbol: str | None = None


class RateResult(BaseModel):
    date: date
    base: str
    quote: str
    rate: Decimal


class ConversionResult(BaseModel):
    amount: Decimal
    converted: Decimal
    rate: Decimal
    rate_date: date
    base: str
    quote: str
    base_name: str | None = None
    quote_name: str | None = None
    base_symbol: str | None = None
    quote_symbol: str | None = None
