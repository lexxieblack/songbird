"""Currency conversion service backed by the Frankfurter API (ECB reference rates)."""

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from cachetools import TTLCache
from structlog import BoundLogger

from songbird.models.currency import ConversionResult, Currency, CurrencyError, RateResult
from songbird.utils.logging import get_logger

_RATE_CACHE_TTL = 12 * 60 * 60
_CURRENCY_CACHE_TTL = 24 * 60 * 60


class CurrencyService:
    def __init__(self, logger: BoundLogger | None = None) -> None:
        self._api_url = "https://api.frankfurter.dev/v2"
        self._logger = logger or get_logger(__name__)
        self._rate_cache: TTLCache[tuple[str, str], RateResult] = TTLCache[tuple[str, str], RateResult](
            maxsize=2048, ttl=_RATE_CACHE_TTL
        )
        self._currency_cache: TTLCache[str, list[Currency]] = TTLCache[str, list[Currency]](maxsize=1, ttl=_CURRENCY_CACHE_TTL)

    async def convert(self, amount: Decimal, base: str, quote: str) -> ConversionResult:
        base = base.strip().upper()
        quote = quote.strip().upper()

        rate = await self.get_rate(base, quote)
        converted = amount * rate.rate

        base_currency, quote_currency = await self._get_currency_names(base, quote)

        return ConversionResult(
            amount=amount,
            converted=converted,
            rate=rate.rate,
            rate_date=rate.date,
            base=base,
            quote=quote,
            base_name=base_currency.name if base_currency else None,
            quote_name=quote_currency.name if quote_currency else None,
            base_symbol=(base_currency.symbol or None) if base_currency else None,
            quote_symbol=(quote_currency.symbol or None) if quote_currency else None,
        )

    async def get_rate(self, base: str, quote: str) -> RateResult:
        base = base.upper()
        quote = quote.upper()

        key = (base, quote)
        cached = self._rate_cache.get(key)
        if cached is not None:
            return cached

        data = await self._get(f"/rate/{base}/{quote}")
        rate = RateResult(
            date=date.fromisoformat(data["date"]),
            base=data["base"],
            quote=data["quote"],
            rate=Decimal(str(data["rate"])),
        )

        self._rate_cache[key] = rate

        self._logger.info("Currency rate fetched", base=base, quote=quote, rate=str(rate.rate))

        return rate

    async def list_currencies(self) -> list[Currency]:
        cached = self._currency_cache.get("all")
        if cached is not None:
            return cached

        data = await self._get("/currencies")
        currencies = [Currency.model_validate(entry) for entry in data]

        self._currency_cache["all"] = currencies

        self._logger.info("Currency list fetched", count=len(currencies))

        return currencies

    async def _get_currency_names(self, base: str, quote: str) -> tuple[Currency | None, Currency | None]:
        try:
            currencies = await self.list_currencies()
        except CurrencyError as e:
            self._logger.warning("Could not load currency names", error=e)
            return None, None

        by_code = {c.iso_code: c for c in currencies}
        return by_code.get(base), by_code.get(quote)

    async def _get(self, path: str) -> Any:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.get(f"{self._api_url}{path}")
        except httpx.TimeoutException as e:
            self._logger.error("Currency request timed out", path=path, error=e)
            raise CurrencyError("Request to the currency service timed out.") from e
        except httpx.RequestError as e:
            self._logger.error("Currency request failed", path=path, error=e)
            raise CurrencyError("Network error while querying the currency service.") from e

        if response.status_code == 422:
            body = response.json()
            detail = body.get("message") if isinstance(body, dict) else None
            message = f"Unknown currency code: {detail}." if detail else "Unknown currency code."
            raise CurrencyError(message)

        if response.is_error:
            self._logger.error("Currency service error", path=path, status_code=response.status_code)
            raise CurrencyError("The currency service returned an error.")

        return response.json()
