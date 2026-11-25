"""Tools cog: translate/file/wolfram/convert/fix/ping behaviour and ban gating."""

import inspect
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest
from discord import File
from discord.commands import AutocompleteContext

from songbird.bot import SongbirdBot
from songbird.cogs.tools import ToolsCog
from songbird.commands.tools.currency import CurrencyHandler
from songbird.models.currency import ConversionResult, Currency, CurrencyError
from songbird.ui.modals.file import FileModal
from songbird.ui.modals.translate import TranslateMessageModal, TranslateModal
from songbird.ui.views.translate import TranslateView
from tests.cogs._support import invoke
from tests.support.discord import FakeCtx, make_message

pytestmark = pytest.mark.discord

COMMANDS: list[tuple[str, dict[str, Any]]] = [
    ("translate", {"text": "hello"}),
    ("translate", {"text": None}),
    ("translate_message", {"message": make_message()}),
    ("file", {}),
    ("wolfram", {"query": "2+2"}),
    ("convert", {"amount": 1.0, "from_": "USD", "to_": "EUR"}),
    ("fix", {"link": "https://example.com"}),
    ("ping", {}),
]


def _fake(ctx: discord.ApplicationContext) -> FakeCtx:
    return cast(FakeCtx, ctx)


def _services(bot: SongbirdBot) -> Any:
    return cast(Any, bot.services)


def _capture_send(ctx: FakeCtx) -> AsyncMock:
    # `followup.send` is called positionally by `/fix`; the shared fake only takes kwargs.
    send = AsyncMock()
    setattr(ctx.followup, "send", send)  # noqa: B010 - mypy forbids assigning a method
    return send


class FakeTranslate:
    def __init__(self, result: tuple[str, str, str] = ("English", "German", "Hallo")) -> None:
        self.result = result
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    async def translate_with_meta(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> tuple[str, str, str]:
        if self.error is not None:
            raise self.error
        self.calls.append({"text": text, "target_lang": target_lang, "source_lang": source_lang})
        return self.result


class FakeWolfram:
    def __init__(self, result: File | None) -> None:
        self.result = result
        self.error: Exception | None = None
        self.queries: list[str] = []

    async def query(self, query: str) -> File | None:
        if self.error is not None:
            raise self.error
        self.queries.append(query)
        return self.result


class FakeFix:
    def __init__(self, result: list[str]) -> None:
        self.result = result
        self.error: Exception | None = None
        self.links: list[str] = []

    async def fix_link(self, link: str) -> list[str]:
        if self.error is not None:
            raise self.error
        self.links.append(link)
        return self.result


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


def _conversion() -> ConversionResult:
    return ConversionResult(
        amount=Decimal("10"),
        converted=Decimal("9.1"),
        rate=Decimal("0.91"),
        rate_date=date(2024, 1, 2),
        base="USD",
        quote="EUR",
    )


@pytest.fixture
def cog(fake_bot: SongbirdBot) -> ToolsCog:
    return ToolsCog(fake_bot)


def test_translate_slash_defaults_to_auto_source_and_english_target() -> None:
    params = inspect.signature(ToolsCog.translate.callback).parameters

    assert params["to_lang"].default.default == "english"
    assert params["from_lang"].default.default == "auto"


async def test_translate_without_text_opens_modal(cog: ToolsCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "translate", fake_ctx, text=None, to_lang="en", from_lang=None)

    assert ctx.defer_calls == []
    method, kwargs = ctx.response.calls[0]
    assert method == "send_modal"
    assert isinstance(kwargs["modal"], TranslateModal)


async def test_translate_sends_result_view(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeTranslate()
    monkeypatch.setattr(cog, "translate_handler", handler)
    ctx = _fake(fake_ctx)

    await invoke(cog, "translate", fake_ctx, text="hello", to_lang="de", from_lang=None)

    assert ctx.defer_calls == [{}]
    assert handler.calls == [{"text": "hello", "target_lang": "de", "source_lang": None}]
    method, kwargs = ctx.followup.calls[0]
    assert method == "send"
    assert isinstance(kwargs["view"], TranslateView)
    assert isinstance(kwargs["allowed_mentions"], discord.AllowedMentions)


async def test_translate_failure_sends_error(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeTranslate()
    handler.error = RuntimeError("boom")
    monkeypatch.setattr(cog, "translate_handler", handler)
    ctx = _fake(fake_ctx)

    await invoke(cog, "translate", fake_ctx, text="hello", to_lang="de", from_lang="en")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Translation failed."


async def test_translate_message_and_file_send_modals(cog: ToolsCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)
    message = make_message()

    await invoke(cog, "translate_message", fake_ctx, message=message)
    await invoke(cog, "file", fake_ctx)

    assert isinstance(ctx.sent_modals[0], TranslateMessageModal)
    assert isinstance(ctx.sent_modals[1], FileModal)


async def test_wolfram_rejects_empty_query(cog: ToolsCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "wolfram", fake_ctx, query="")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Please provide a query for Wolfram Alpha."


async def test_wolfram_sends_file(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    gif = File(fp=BytesIO(b"gif"), filename="wolfram.gif")
    handler = FakeWolfram(gif)
    monkeypatch.setattr(cog, "wolfram_handler", handler)
    ctx = _fake(fake_ctx)

    await invoke(cog, "wolfram", fake_ctx, query="2+2")

    assert ctx.defer_calls == [{}]
    assert handler.queries == ["2+2"]
    assert ctx.followup.calls[0][1]["file"] is gif
    assert ctx.followup.calls[0][1]["embed"].image.url == "attachment://wolfram.gif"
    assert ctx.followup.calls[0][1]["allowed_mentions"].everyone is False


async def test_wolfram_failure_sends_error(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeWolfram(None)
    monkeypatch.setattr(cog, "wolfram_handler", handler)
    ctx = _fake(fake_ctx)

    await invoke(cog, "wolfram", fake_ctx, query="2+2")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Wolfram query failed."


async def test_convert_sends_formatted_embed(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = FakeCurrencyService(_conversion())
    monkeypatch.setattr(cog, "currency_handler", CurrencyHandler(cast(Any, service)))
    ctx = _fake(fake_ctx)

    await invoke(cog, "convert", fake_ctx, amount=10.0, from_="usd", to_="eur")

    assert ctx.defer_calls == [{}]
    assert service.calls == [(Decimal("10.0"), "usd", "eur")]
    embed = ctx.followup.calls[0][1]["embed"]
    assert embed.title == "Currency Conversion"
    assert embed.description.startswith("**10 USD = 9.1 EUR**")


async def test_convert_rejects_zero_amount(cog: ToolsCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "convert", fake_ctx, amount=0.0, from_="usd", to_="eur")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Amount must be greater than zero."


async def test_convert_reports_service_error(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = FakeCurrencyService(_conversion())
    service.error = CurrencyError("Unknown currency code: XXX")
    monkeypatch.setattr(cog, "currency_handler", CurrencyHandler(cast(Any, service)))
    ctx = _fake(fake_ctx)

    await invoke(cog, "convert", fake_ctx, amount=1.0, from_="usd", to_="xxx")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Unknown currency code: XXX"


async def test_fix_sends_formatted_links(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeFix(["https://example.com/a"])
    monkeypatch.setattr(cog, "fix_handler", handler)

    def extract(_url: str) -> SimpleNamespace:
        return SimpleNamespace(domain="example", suffix="com")

    monkeypatch.setattr("songbird.cogs.tools._EXTRACT", extract)
    send = _capture_send(_fake(fake_ctx))

    await invoke(cog, "fix", fake_ctx, link="https://example.com/a")

    assert handler.links == ["https://example.com/a"]
    assert send.await_args is not None
    assert send.await_args.args[0] == "[example.com](https://example.com/a)"


async def test_fix_rejects_empty_link(cog: ToolsCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "fix", fake_ctx, link="")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Please provide a link to fix."


async def test_fix_rejects_non_url(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeFix([])
    monkeypatch.setattr(cog, "fix_handler", handler)
    ctx = _fake(fake_ctx)

    await invoke(cog, "fix", fake_ctx, link="not a link")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Please provide a valid http(s) link."
    assert handler.links == []
    assert ctx.defer_calls == []


async def test_ping_reports_latency(cog: ToolsCog, fake_bot: SongbirdBot, fake_ctx: discord.ApplicationContext) -> None:
    cast(Any, fake_bot).latency = 0.123
    ctx = _fake(fake_ctx)

    await invoke(cog, "ping", fake_ctx)

    assert ctx.respond_calls[0]["args"] == (":satellite: `123`ms",)


async def test_currency_autocomplete_filters_currencies(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
) -> None:
    service = FakeCurrencyService()
    service.currencies = [Currency(iso_code="USD", name="United States Dollar"), Currency(iso_code="EUR", name="Euro")]
    monkeypatch.setattr(cog, "currency_handler", CurrencyHandler(cast(Any, service)))

    choices = await cog.currency_autocomplete(cast(AutocompleteContext, SimpleNamespace(value="eu")))

    assert [choice.value for choice in choices] == ["EUR"]


async def test_currency_autocomplete_swallows_errors(
    monkeypatch: pytest.MonkeyPatch,
    cog: ToolsCog,
) -> None:
    handler = SimpleNamespace(autocomplete=AsyncMock(side_effect=RuntimeError("down")))
    monkeypatch.setattr(cog, "currency_handler", handler)

    assert await cog.currency_autocomplete(cast(AutocompleteContext, SimpleNamespace(value="usd"))) == []
