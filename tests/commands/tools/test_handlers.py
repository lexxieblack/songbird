"""Tool command handlers: currency formatting, link fixing, translation and wolfram IO."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from songbird.commands.tools.currency import CurrencyHandler
from songbird.commands.tools.fix import FixHandler
from songbird.commands.tools.translate import TranslateHandler
from songbird.commands.tools.wolfram import WolframHandler
from songbird.models.currency import ConversionResult, Currency, CurrencyError


class FakeCurrencyService:
    def __init__(self, result: ConversionResult | None = None) -> None:
        self.result = result
        self.error: Exception | None = None
        self.calls: list[tuple[Decimal, str, str]] = []
        self.currencies: list[Currency] = []

    async def convert(self, amount: Decimal, base: str, quote: str) -> ConversionResult:
        if self.error is not None:
            raise self.error
        self.calls.append((amount, base, quote))
        assert self.result is not None
        return self.result

    async def list_currencies(self) -> list[Currency]:
        if self.error is not None:
            raise self.error
        return self.currencies


class FakeLinkFixer:
    def __init__(self, result: list[str]) -> None:
        self.result = result
        self.links: list[str] = []

    async def fix(self, text: str) -> list[str]:
        self.links.append(text)
        return self.result


class FakeTranslation:
    def __init__(self) -> None:
        self.translated = "Hallo"
        self.detected = "de"
        self.calls: list[tuple[str, str, str]] = []
        self.detections: list[str] = []

    async def translate(self, text: str, target_lang: str, source_lang: str) -> str:
        self.calls.append((text, target_lang, source_lang))
        return self.translated

    async def detect_language(self, text: str) -> str:
        self.detections.append(text)
        return self.detected

    def get_language_name(self, language: str) -> str:
        return {"en": "English", "de": "German", "auto": "Auto"}.get(language, language)


class FakeWolfram:
    def __init__(self, result: bytes) -> None:
        self.result = result
        self.error: Exception | None = None
        self.queries: list[str] = []

    async def query(self, question: str) -> bytes:
        if self.error is not None:
            raise self.error
        self.queries.append(question)
        return self.result


def _conversion(
    amount: str = "10",
    converted: str = "9.1",
    rate: str = "0.912345",
    base_symbol: str | None = None,
    quote_symbol: str | None = None,
) -> ConversionResult:
    return ConversionResult(
        amount=Decimal(amount),
        converted=Decimal(converted),
        rate=Decimal(rate),
        rate_date=date(2024, 1, 2),
        base="USD",
        quote="EUR",
        base_symbol=base_symbol,
        quote_symbol=quote_symbol,
    )


async def test_currency_autocomplete_filters_and_sorts() -> None:
    service = FakeCurrencyService()
    service.currencies = [
        Currency(iso_code="USD", name="United States Dollar"),
        Currency(iso_code="EUR", name="Euro"),
        Currency(iso_code="AUD", name="Australian Dollar"),
    ]
    handler = CurrencyHandler(cast(Any, service))

    choices = await handler.autocomplete("dollar")

    assert [choice.value for choice in choices] == ["AUD", "USD"]


async def test_currency_convert_rejects_non_positive_amount() -> None:
    service = FakeCurrencyService(_conversion())
    handler = CurrencyHandler(cast(Any, service))

    with pytest.raises(CurrencyError, match="Amount must be greater than zero."):
        await handler.convert(0, "USD", "EUR")

    assert service.calls == []


async def test_currency_convert_forwards_decimal() -> None:
    service = FakeCurrencyService(_conversion())
    handler = CurrencyHandler(cast(Any, service))

    result = await handler.convert(10.5, "usd", "eur")

    assert result.converted == Decimal("9.1")
    assert service.calls == [(Decimal("10.5"), "usd", "eur")]


def test_currency_format_result_uses_symbols() -> None:
    handler = CurrencyHandler(cast(Any, FakeCurrencyService()))

    text = handler.format_result(_conversion(base_symbol="$", quote_symbol="€"))

    assert text == "\n".join(
        [
            "**10 $ = 9.1 €**",
            "Rate: 1 USD = 0.9123 EUR",
            "ECB reference rates as of 2024-01-02",
        ]
    )


def test_currency_format_result_keeps_sub_cent_amounts() -> None:
    # Regression: `0.001 BTC` was rendered as `0 BTC`.
    handler = CurrencyHandler(cast(Any, FakeCurrencyService()))
    result = _conversion(amount="0.001", converted="100", rate="100000", base_symbol="BTC", quote_symbol="USD")

    assert handler.format_result(result).splitlines()[0] == "**0.001 BTC = 100 USD**"


def test_currency_format_amount_trims_and_keeps_precision() -> None:
    handler = CurrencyHandler(cast(Any, FakeCurrencyService()))

    assert handler.format_result(_conversion(amount="0.0001", converted="10")).splitlines()[0] == "**0.0001 USD = 10 EUR**"
    assert handler.format_result(_conversion(amount="1234567.891")).splitlines()[0] == "**1,234,567.89 USD = 9.1 EUR**"


async def test_fix_handler_delegates_and_records() -> None:
    service = FakeLinkFixer(["https://example.com/fixed"])
    handler = FixHandler(cast(Any, service))

    result = await handler.fix_link("https://example.com")

    assert result == ["https://example.com/fixed"]
    assert service.links == ["https://example.com"]


async def test_translate_with_explicit_source_skips_detection() -> None:
    service = FakeTranslation()
    handler = TranslateHandler(cast(Any, service))

    result = await handler.translate_with_meta("hello", "de", "en")

    assert result == ("English", "German", "Hallo")
    assert service.calls == [("hello", "de", "en")]
    assert service.detections == []


async def test_translate_auto_detects_source() -> None:
    service = FakeTranslation()
    handler = TranslateHandler(cast(Any, service))

    result = await handler.translate_with_meta("hello", "de", None)

    assert result == ("German", "German", "Hallo")
    assert service.calls == [("hello", "de", "auto")]
    assert service.detections == ["hello"]


async def test_translate_plain_forwards() -> None:
    service = FakeTranslation()
    handler = TranslateHandler(cast(Any, service))

    assert await handler.translate("hello", "de", None) == "Hallo"
    assert service.calls == [("hello", "de", "auto")]


async def test_wolfram_handler_returns_gif_file() -> None:
    service = FakeWolfram(b"gif-bytes")
    handler = WolframHandler(cast(Any, service))

    result = await handler.query("2+2")

    assert result is not None
    assert result.filename == "wolfram.gif"
    assert service.queries == ["2+2"]


async def test_wolfram_handler_swallows_service_errors() -> None:
    service = FakeWolfram(b"unused")
    service.error = RuntimeError("down")
    handler = WolframHandler(cast(Any, service))

    assert await handler.query("2+2") is None
