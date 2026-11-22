from decimal import Decimal

import httpx
import pytest
import respx

from songbird.models.currency import Currency, CurrencyError
from songbird.services.currency import CurrencyService

BASE = "https://api.frankfurter.dev/v2"
CURRENCIES = [
    {"iso_code": "USD", "name": "United States Dollar", "symbol": "$"},
    {"iso_code": "EUR", "name": "Euro", "symbol": "€"},
]


@pytest.fixture
def service() -> CurrencyService:
    return CurrencyService()


def _rate_route(respx_mock: respx.MockRouter) -> respx.Route:
    return respx_mock.get(f"{BASE}/rate/USD/EUR").mock(
        return_value=httpx.Response(200, json={"date": "2024-01-02", "base": "USD", "quote": "EUR", "rate": 0.91})
    )


async def test_get_rate_parses_and_caches(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    route = _rate_route(respx_mock)

    first = await service.get_rate("usd", "eur")
    second = await service.get_rate("USD", "EUR")

    assert first.base == "USD"
    assert first.quote == "EUR"
    assert first.rate == Decimal("0.91")
    assert second is first
    assert route.call_count == 1


async def test_convert_returns_names_and_symbols(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    _rate_route(respx_mock)
    respx_mock.get(f"{BASE}/currencies").mock(return_value=httpx.Response(200, json=CURRENCIES))

    result = await service.convert(Decimal("10"), "usd", "eur")

    assert result.amount == Decimal("10")
    assert result.converted == Decimal("9.10")
    assert result.rate == Decimal("0.91")
    assert result.base_name == "United States Dollar"
    assert result.quote_name == "Euro"
    assert result.base_symbol == "$"
    assert result.quote_symbol == "€"


async def test_convert_survives_currency_list_failure(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    _rate_route(respx_mock)
    respx_mock.get(f"{BASE}/currencies").mock(return_value=httpx.Response(500))

    result = await service.convert(Decimal("1"), "USD", "EUR")

    assert result.converted == Decimal("0.91")
    assert result.base_name is None
    assert result.quote_name is None


async def test_list_currencies_parses_and_caches(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/currencies").mock(return_value=httpx.Response(200, json=CURRENCIES))

    first = await service.list_currencies()
    second = await service.list_currencies()

    assert first == [Currency.model_validate(entry) for entry in CURRENCIES]
    assert second is first
    assert route.call_count == 1


async def test_unknown_currency_uses_api_detail(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{BASE}/rate/USD/XXX").mock(return_value=httpx.Response(422, json={"message": "not found: XXX"}))

    with pytest.raises(CurrencyError, match="Unknown currency code: not found: XXX"):
        await service.get_rate("USD", "XXX")


async def test_unknown_currency_without_detail(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{BASE}/rate/USD/XXX").mock(return_value=httpx.Response(422, json={}))

    with pytest.raises(CurrencyError, match="Unknown currency code"):
        await service.get_rate("USD", "XXX")


async def test_server_error_raises_currency_error(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{BASE}/currencies").mock(return_value=httpx.Response(503))

    with pytest.raises(CurrencyError, match="returned an error"):
        await service.list_currencies()


async def test_timeout_raises_currency_error(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{BASE}/currencies").mock(side_effect=httpx.TimeoutException("slow"))

    with pytest.raises(CurrencyError, match="timed out"):
        await service.list_currencies()


async def test_network_error_raises_currency_error(service: CurrencyService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{BASE}/currencies").mock(side_effect=httpx.ConnectError("offline"))

    with pytest.raises(CurrencyError, match="Network error"):
        await service.list_currencies()
