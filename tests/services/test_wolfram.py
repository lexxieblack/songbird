import httpx
import pytest
import respx

from songbird.config import Settings
from songbird.services.wolfram import WolframService

URL = "https://api.wolframalpha.com/v1/simple"


@pytest.fixture
def service(settings: Settings) -> WolframService:
    return WolframService(settings)


async def test_query_returns_image_bytes(service: WolframService, respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, content=b"GIF89a"))

    assert await service.query("2+2") == b"GIF89a"

    request = route.calls[0].request  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
    assert request.url.params["i"] == "2+2"  # pyright: ignore[reportUnknownMemberType]
    assert request.url.params["appid"] == "test-wolfram-key"  # pyright: ignore[reportUnknownMemberType]
    assert "background" not in request.url.params  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (501, "could not understand"),
        (400, "Invalid query format"),
        (500, "Error querying"),
    ],
)
async def test_error_statuses_raise(service: WolframService, respx_mock: respx.MockRouter, status: int, message: str) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(status))

    with pytest.raises(Exception, match=message):
        await service.query("nonsense")


async def test_empty_result_raises(service: WolframService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, content=b""))

    with pytest.raises(Exception, match="No result"):
        await service.query("nothing")


async def test_timeout_raises_friendly_error(service: WolframService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.TimeoutException("slow"))

    with pytest.raises(Exception, match="timed out"):
        await service.query("slow")


async def test_network_error_raises_friendly_error(service: WolframService, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("no route"))

    with pytest.raises(Exception, match="Network error"):
        await service.query("offline")
