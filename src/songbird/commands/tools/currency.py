"""Currency conversion command handler."""

from decimal import Decimal

import discord

from songbird.services.currency import ConversionResult, Currency, CurrencyError, CurrencyService
from songbird.utils.logging import get_logger


class CurrencyHandler:
    def __init__(self, currency_service: CurrencyService) -> None:
        self.service = currency_service
        self.logger = get_logger(__name__)

    async def autocomplete(self, query: str) -> list[discord.OptionChoice]:
        currencies = await self.service.list_currencies()

        return [_choice(c) for c in _match_currencies(currencies, query)[:25]]

    async def convert(self, amount: float, base: str, to: str) -> ConversionResult:
        if amount <= 0:
            raise CurrencyError("Amount must be greater than zero.")

        self.logger.debug("Converting currency", amount=amount, base=base, to=to)

        return await self.service.convert(Decimal(str(amount)), base, to)

    def format_result(self, result: ConversionResult) -> str:
        base_display = result.base_symbol or result.base
        quote_display = result.quote_symbol or result.quote

        return "\n".join(
            [
                f"**{_format_amount(result.amount)} {base_display} = {_format_amount(result.converted)} {quote_display}**",
                f"Rate: 1 {result.base} = {_format_rate(result.rate)} {result.quote}",
                f"ECB reference rates as of {result.rate_date.isoformat()}",
            ]
        )


def _match_currencies(currencies: list[Currency], query: str) -> list[Currency]:
    query = query.strip().lower()
    if query:
        matches = [c for c in currencies if query in c.iso_code.lower() or query in c.name.lower()]
        matches.sort(key=lambda c: (not c.iso_code.lower().startswith(query), c.iso_code))
        return matches

    return sorted(currencies, key=lambda c: c.iso_code)


def _choice(currency: Currency) -> discord.OptionChoice:
    return discord.OptionChoice(name=f"{currency.iso_code} — {currency.name}", value=currency.iso_code)


def _format_amount(value: Decimal) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _format_rate(value: Decimal) -> str:
    return f"{value:,.4f}".rstrip("0").rstrip(".")
