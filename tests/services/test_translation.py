from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any, cast

import pytest

from songbird.services.translation import TranslationService


class _Translator:
    def __init__(self, text: str = "translated", lang: str = "en") -> None:
        self.text = text
        self.lang = lang
        self.calls: list[tuple[str, str, str]] = []
        self.detected: list[str] = []

    async def translate(self, text: str, src: str, dest: str) -> SimpleNamespace:
        self.calls.append((text, src, dest))
        return SimpleNamespace(text=self.text)

    async def detect(self, text: str) -> SimpleNamespace:
        self.detected.append(text)
        return SimpleNamespace(lang=self.lang)


@pytest.fixture
async def service() -> AsyncIterator[TranslationService]:
    translation = TranslationService()
    yield translation
    await translation.close()


def _install(monkeypatch: pytest.MonkeyPatch, service: TranslationService, translator: _Translator) -> _Translator:
    monkeypatch.setattr(service, "translator", cast(Any, translator))
    return translator


def test_language_code_lookup(service: TranslationService) -> None:
    assert service.get_language_code("English") == "en"
    assert service.get_language_code("ja") == "ja"
    assert service.get_language_code("Notalanguage") is None


def test_language_name_lookup(service: TranslationService) -> None:
    assert service.get_language_name("en") == "English"
    assert service.get_language_name("German") == "German"
    assert service.get_language_name("zz") == "zz"
    assert service.get_language_name("Klingon") == "Klingon"


async def test_translate_uses_codes_and_returns_text(monkeypatch: pytest.MonkeyPatch, service: TranslationService) -> None:
    translator = _install(monkeypatch, service, _Translator("Hallo"))

    assert await service.translate("hello", "German", "English") == "Hallo"
    assert translator.calls == [("hello", "en", "de")]


async def test_translate_unknown_source_falls_back_to_auto(monkeypatch: pytest.MonkeyPatch, service: TranslationService) -> None:
    translator = _install(monkeypatch, service, _Translator())

    await service.translate("hello", "German", "Notalanguage")

    assert translator.calls == [("hello", "auto", "de")]


async def test_translate_rejects_unknown_target(monkeypatch: pytest.MonkeyPatch, service: TranslationService) -> None:
    translator = _install(monkeypatch, service, _Translator())

    result = await service.translate("hello", "Notalanguage", "English")

    assert result == "Error: target language not supported"
    assert translator.calls == []


async def test_translate_failure_returns_error_message(monkeypatch: pytest.MonkeyPatch, service: TranslationService) -> None:
    class _Broken(_Translator):
        async def translate(self, _text: str, _src: str, _dest: str) -> SimpleNamespace:  # pyright: ignore[reportIncompatibleMethodOverride]
            raise RuntimeError("upstream down")

    _install(monkeypatch, service, _Broken())

    assert await service.translate("hello", "German", "English") == "Error: failed to translate text"


async def test_detect_language(monkeypatch: pytest.MonkeyPatch, service: TranslationService) -> None:
    translator = _install(monkeypatch, service, _Translator(lang="fr"))

    assert await service.detect_language("bonjour") == "fr"
    assert translator.detected == ["bonjour"]


async def test_close_closes_client(monkeypatch: pytest.MonkeyPatch, service: TranslationService) -> None:
    closed: list[bool] = []

    class _Client:
        async def aclose(self) -> None:
            closed.append(True)

    monkeypatch.setattr(service, "_client", cast(Any, _Client()))

    await service.close()

    assert closed == [True]
