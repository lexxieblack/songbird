from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from songbird.models._base_db_model import BaseDBModel
from songbird.models.chat.base import MessageRole
from songbird.models.chat.guild_message import GuildMessage
from songbird.models.chat.message import Message
from songbird.models.conversation import ConversationContext
from songbird.models.currency import ConversionResult, Currency, CurrencyError, RateResult
from songbird.models.exception import SongbirdException
from songbird.models.help import CategoryDef, HelpCommandEntry
from songbird.models.llm import LLMRequest

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


class _Point(BaseDBModel):
    x: int


def test_base_db_model_reads_attributes_and_ignores_extras() -> None:
    point = _Point.model_validate(SimpleNamespace(x=3, y=4))

    assert point == _Point(x=3)


def test_conversation_context_defaults_optional_fields_to_none() -> None:
    context = ConversationContext(user_id=1, username="alice", display_name="Alice")

    assert context.guild_name is None
    assert context.channel_name is None


def test_conversation_context_accepts_guild_and_channel() -> None:
    context = ConversationContext(
        user_id=1, username="alice", display_name="Alice", guild_name="Night City", channel_name="general"
    )

    assert context.guild_name == "Night City"
    assert context.channel_name == "general"


@pytest.mark.parametrize("missing", ["user_id", "username", "display_name"])
def test_conversation_context_requires_identity_fields(missing: str) -> None:
    values: dict[str, object] = {"user_id": 1, "username": "alice", "display_name": "Alice"}
    values.pop(missing)

    with pytest.raises(ValidationError):
        ConversationContext(**values)  # type: ignore[arg-type]


def test_currency_symbol_defaults_to_none() -> None:
    assert Currency(iso_code="USD", name="US Dollar").symbol is None


def test_rate_result_parses_date_and_decimal() -> None:
    result = RateResult.model_validate({"date": "2026-01-02", "base": "USD", "quote": "EUR", "rate": "0.91"})

    assert result.date == datetime(2026, 1, 2).date()
    assert result.rate == Decimal("0.91")


def test_conversion_result_optional_names_and_symbols_default_to_none() -> None:
    result = ConversionResult.model_validate(
        {
            "amount": "10",
            "converted": "9.1",
            "rate": "0.91",
            "rate_date": "2026-01-02",
            "base": "USD",
            "quote": "EUR",
        }
    )

    assert result.amount == Decimal("10")
    assert result.converted == Decimal("9.1")
    assert result.base_name is None
    assert result.quote_symbol is None


def test_currency_error_carries_data_as_a_songbird_exception() -> None:
    error = CurrencyError("conversion failed", {"base": "USD"})

    assert isinstance(error, SongbirdException)
    assert str(error) == "conversion failed"
    assert error.data == {"base": "USD"}


def test_llm_request_defaults_optional_fields() -> None:
    request = LLMRequest(user_prompt="hello")

    assert request.system_prompt is None
    assert request.context_messages is None


def test_llm_request_accepts_private_messages() -> None:
    message = Message(id=uuid4(), user_id=1, role=MessageRole.USER, content="hi", created_at=NOW)

    request = LLMRequest(user_prompt="hello", context_messages=[message])

    assert request.context_messages == [message]


def test_llm_request_accepts_guild_messages() -> None:
    message = GuildMessage(id=uuid4(), guild_id=1, role=MessageRole.MODEL, content="hi", created_at=NOW)

    request = LLMRequest(user_prompt="hello", context_messages=[message])

    assert request.context_messages == [message]


def test_llm_request_requires_a_user_prompt() -> None:
    with pytest.raises(ValidationError):
        LLMRequest()  # type: ignore[call-arg]


def test_songbird_exception_defaults_to_empty_data() -> None:
    error = SongbirdException("boom")

    assert str(error) == "boom"
    assert error.data == {}


def test_songbird_exception_data_is_per_instance() -> None:
    first = SongbirdException("one")
    second = SongbirdException("two")

    assert first.data is not second.data


def test_songbird_exception_exposes_passed_data() -> None:
    data: dict[str, object] = {"guild_id": 1, "reason": "spam"}

    assert SongbirdException("boom", data).data == data


def test_songbird_exception_with_explicit_none_data() -> None:
    assert SongbirdException("boom", None).data == {}


def test_category_def_requires_all_fields() -> None:
    category = CategoryDef(label="General", emoji="❓", description="General commands")

    assert category.label == "General"

    with pytest.raises(ValidationError):
        CategoryDef(label="General", emoji="❓")  # type: ignore[call-arg]


def test_help_command_entry_defaults_emoji_to_none() -> None:
    entry = HelpCommandEntry(
        key="help",
        label="Help",
        description="Show help",
        short_description="Help",
        category="general",
    )

    assert entry.emoji is None


def test_help_command_entry_keeps_an_emoji() -> None:
    entry = HelpCommandEntry(
        key="help",
        label="Help",
        emoji="❓",
        description="Show help",
        short_description="Help",
        category="general",
    )

    assert entry.emoji == "❓"
